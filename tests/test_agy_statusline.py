import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUSLINE = ROOT / "dot_gemini/antigravity-cli/executable_statusline.sh"
MODIFY_SETTINGS = ROOT / "dot_gemini/antigravity-cli/modify_private_settings.json"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def run_statusline(payload: dict, *, cwd: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(STATUSLINE)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
    )


class AgyStatuslineTest(unittest.TestCase):
    def test_settings_json_enables_altscreen_and_statusline(self):
        result = subprocess.run(
            [str(MODIFY_SETTINGS)],
            input="",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["altScreenMode"], "always")
        self.assertEqual(
            data["statusLine"],
            {
                "command": "~/.gemini/antigravity-cli/statusline.sh",
                "type": "command",
            },
        )
        self.assertNotIn("trustedWorkspaces", data)

    def test_renders_model_pwd_branch_pr_context_quota_and_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            repo = home / "work" / "demo"
            repo.mkdir(parents=True)
            cache_home = tmp_path / "cache"
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()

            subprocess.run(["git", "init", "-b", "feat/status-bar"], cwd=repo, check=True, capture_output=True)

            # Fake gh returning PR #42 synchronously for the background refresh test.
            fake_gh = fake_bin / "gh"
            fake_gh.write_text("#!/usr/bin/env bash\necho 42\n", encoding="utf-8")
            fake_gh.chmod(0o755)

            # Pre-populate cache to deterministically assert PR rendering.
            cache_dir = cache_home / "agy-statusline"
            cache_dir.mkdir(parents=True)
            cksum = subprocess.run(
                ["cksum"],
                input=f"{repo}|feat/status-bar".encode(),
                capture_output=True,
                check=True,
            ).stdout.decode().strip().replace(" ", "_").replace("\t", "_")
            cache_file = cache_dir / f"pr-{cksum}"
            cache_file.write_text(f"{int(2e9)} 42\n", encoding="utf-8")

            payload = {
                "cwd": str(repo),
                "workspace": {"current_dir": str(repo), "project_dir": str(repo)},
                "model": {
                    "id": "Gemini 4 Neon (High)",
                    "display_name": "Gemini 4 Neon (High)",
                    "effort": "high",
                },
                "cycle_mode": "plan",
                "context_window": {
                    "total_input_tokens": 88244,
                    "total_output_tokens": 61074,
                    "context_window_size": 1048576,
                    "used_percentage": 14.24,
                    "remaining_percentage": 85.76,
                },
                "quota": {
                    "gemini-weekly": {
                        "remaining_fraction": 0.9378,
                        "reset_in_seconds": 560580,
                    },
                    "gemini-five-hour": {
                        "remaining_fraction": 0.62,
                        "reset_in_seconds": 11520,
                    },
                    "3p-five-hour": {
                        "remaining_fraction": 0.05,
                        "reset_in_seconds": 7200,
                    },
                    "disabled-bucket": {
                        "remaining_fraction": 0.0,
                        "disabled": True,
                    },
                },
                "subagents": [
                    {"name": "a1", "role": "research", "status": "running"},
                    {"name": "a2", "role": "review", "status": "completed"},
                ],
                "task_count": 2,
            }

            result = run_statusline(
                payload,
                cwd=repo,
                env_extra={
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(cache_home),
                    "PATH": f"{fake_bin}:{os.environ['PATH']}",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plain = strip_ansi(result.stdout)
            self.assertIn("Gemini 4 Neon (High) [plan]", plain)
            self.assertIn("~/work/demo (feat/status-bar #42)", plain)
            self.assertIn("ctx █░░░░░░░░░ 14% 149k/1.0M", plain)
            # 5h bucket (shorter reset) appears before 7d bucket.
            idx_5h = plain.index("gemini-5h 62% ·3h12m")
            idx_7d = plain.index("gemini-7d 94% ·6d11h")
            self.assertLess(idx_5h, idx_7d)
            self.assertNotIn("disabled-bucket", plain)
            self.assertNotIn("3p-5h", plain)
            self.assertIn("1ag 2bg", plain)
            self.assertNotIn("Low quota", plain)
            self.assertNotIn("[bypass]", plain)

    def test_low_quota_warning_and_zero_context_before_first_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            work = home / "plain"
            work.mkdir(parents=True)

            payload = {
                "cwd": str(work),
                "model": {
                    "id": "gemini-4-neon",
                    "display_name": "Gemini 4 Neon",
                    "effort": "high",
                },
                "context_window": {
                    "context_window_size": 1048576,
                    "used_percentage": None,
                },
                "quota": {
                    "gemini-weekly": {
                        "remaining_fraction": 0.08,
                        "reset_in_seconds": 3600,
                    },
                    "ai-credits": {
                        "remaining_amount": 42,
                    },
                },
            }

            result = run_statusline(
                payload,
                cwd=work,
                env_extra={
                    "HOME": str(home),
                    "XDG_CACHE_HOME": str(tmp_path / "cache"),
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plain = strip_ansi(result.stdout)
            self.assertIn("Gemini 4 Neon (high)", plain)
            self.assertIn("~/plain", plain)
            self.assertIn("ctx ░░░░░░░░░░ 0% 0/1.0M", plain)
            self.assertIn("ai-credits 42", plain)
            self.assertIn("gemini-7d 8% ·1h", plain)
            self.assertIn("Low quota (<10%)", plain)

    def test_shows_bypass_when_invoked_by_agy_with_skip_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            work = home / "work"
            work.mkdir(parents=True)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["XDG_CACHE_HOME"] = str(tmp_path / "cache")

            base_payload = {
                "cwd": str(work),
                "model": {"id": "gemini-4-neon", "display_name": "Gemini 4 Neon"},
            }

            # 1) Direct parent `agy --dangerously-skip-permissions` in default mode.
            res_direct = subprocess.run(
                [
                    "bash",
                    "-c",
                    'exec -a agy bash -c \'bash "$2"; :\' _ --dangerously-skip-permissions "$0"',
                    str(STATUSLINE),
                ],
                input=json.dumps(base_payload),
                text=True,
                capture_output=True,
                cwd=str(work),
                env=env,
                check=False,
            )
            self.assertEqual(res_direct.returncode, 0, res_direct.stderr)
            plain_direct = strip_ansi(res_direct.stdout)
            self.assertIn("[bypass]", plain_direct)
            self.assertNotIn("[auto]", plain_direct)

            # 2) Grandparent `agy --dangerously-skip-permissions` via intermediate `sh -c`, plus plan mode.
            res_sh = subprocess.run(
                [
                    "bash",
                    "-c",
                    'exec -a agy bash -c \'sh -c "bash \\"\\$1\\"; :" _ "$2"; :\' _ --dangerously-skip-permissions "$0"',
                    str(STATUSLINE),
                ],
                input=json.dumps({**base_payload, "cycle_mode": "plan"}),
                text=True,
                capture_output=True,
                cwd=str(work),
                env=env,
                check=False,
            )
            self.assertEqual(res_sh.returncode, 0, res_sh.stderr)
            self.assertIn("[plan] [bypass]", strip_ansi(res_sh.stdout))

            # 3) Parent `agy` without `--dangerously-skip-permissions`.
            res_no_bypass = subprocess.run(
                [
                    "bash",
                    "-c",
                    'exec -a agy bash -c \'bash "$2"; :\' _ --mode=auto "$0"',
                    str(STATUSLINE),
                ],
                input=json.dumps({**base_payload, "cycle_mode": "auto"}),
                text=True,
                capture_output=True,
                cwd=str(work),
                env=env,
                check=False,
            )
            self.assertEqual(res_no_bypass.returncode, 0, res_no_bypass.stderr)
            plain_no_bypass = strip_ansi(res_no_bypass.stdout)
            self.assertIn("[auto]", plain_no_bypass)
            self.assertNotIn("[bypass]", plain_no_bypass)


if __name__ == "__main__":
    unittest.main()
