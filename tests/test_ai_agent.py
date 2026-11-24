"""Verify ai-agent selects between ay and ai-round cleanly and preserves exec semantics."""

import json
import os
from pathlib import Path
import pty
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "private_dot_local/bin/executable_ai-agent"

BACKEND_STUB = r'''#!/usr/bin/env python3
import json
import os
import sys

if os.isatty(0):
    with open(os.environ["STUB_LOG"], "w", encoding="utf-8") as handle:
        json.dump(
            {
                "backend": os.environ["STUB_NAME"],
                "args": sys.argv[1:],
                "pid": os.getpid(),
                "pgrp": os.getpgrp(),
                "tty": os.ttyname(0),
            },
            handle,
        )
    sys.exit(0)

print(json.dumps({"backend": os.environ["STUB_NAME"], "args": sys.argv[1:]}))
sys.exit(0)
'''

CLAUDE_ACCOUNT_STUB = r'''#!/usr/bin/env python3
import os
import sys

if sys.argv[1:] == ["usage-snapshot"]:
    if os.environ.get("CLAUDE_SNAPSHOT_FAIL") == "1":
        sys.stderr.write("usage-snapshot failed\n")
        sys.exit(1)
    sys.stdout.write(os.environ["CLAUDE_SNAPSHOT_JSON"])
    sys.exit(0)
sys.exit(2)
'''


class AiAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="ai-agent-test-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.quota_file = self.root / "state" / "agy-statusline" / "quota.json"
        self.quota_file.parent.mkdir(parents=True)
        self.log = self.root / "exec.json"

        self.ay_bin = self._write_stub(
            self.bin_dir / "ay",
            BACKEND_STUB.replace('os.environ["STUB_NAME"]', '"ay"'),
        )
        self.ai_round_bin = self._write_stub(
            self.bin_dir / "ai-round",
            BACKEND_STUB.replace('os.environ["STUB_NAME"]', '"ai-round"'),
        )
        self.claude_account_bin = self._write_stub(
            self.bin_dir / "claude-account",
            CLAUDE_ACCOUNT_STUB,
        )
        self.now = int(time.time())
        self.env = {
            **os.environ,
            "PATH": f"{self.bin_dir}:/usr/bin:/bin",
            "AI_AGENT_AY_BIN": str(self.ay_bin),
            "AI_AGENT_AI_ROUND_BIN": str(self.ai_round_bin),
            "AI_AGENT_CLAUDE_ACCOUNT_BIN": str(self.claude_account_bin),
            "AI_AGENT_AGY_QUOTA_FILE": str(self.quota_file),
            "STUB_LOG": str(self.log),
            "CLAUDE_SNAPSHOT_JSON": json.dumps([]),
        }
        for var in ("AI_AGENT_BACKEND", "AI_AGENT_PREFER", "AI_AGENT_MIN_REMAINING", "FORCE_COLOR"):
            self.env.pop(var, None)

    def _write_stub(self, path: Path, body: str) -> Path:
        path.write_text(
            body.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1),
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def _write_agy_quota(
        self,
        *,
        five_h: int | None = 80,
        seven_d: int | None = 85,
        reset_5h: int = 3600,
        reset_7d: int = 86400,
        observed_at: float | None = None,
    ) -> None:
        buckets: dict[str, dict[str, int]] = {}
        if five_h is not None:
            buckets["gemini-5h"] = {"remaining_pct": five_h, "reset_in_seconds": reset_5h}
        if seven_d is not None:
            buckets["gemini-7d"] = {"remaining_pct": seven_d, "reset_in_seconds": reset_7d}
        payload = {
            "observed_at": self.now if observed_at is None else observed_at,
            "buckets": buckets,
        }
        self.quota_file.write_text(json.dumps(payload), encoding="utf-8")

    def _claude_snapshot(self, *accounts: tuple[str, list[float | None], str | None]) -> str:
        rows = []
        for name, rem, unavail in accounts:
            selector = "login" if name == "ai-login" else name.removeprefix("ai")
            rows.append(
                {
                    "name": name,
                    "selector": selector,
                    "remaining": rem,
                    "source": "statusline",
                    "observed_at": float(self.now),
                    "unavailable": unavail,
                }
            )
        return json.dumps(rows)

    def run_cli(
        self,
        *args: str,
        env_extra: dict[str, str] | None = None,
        stdin: str = "",
    ) -> subprocess.CompletedProcess[str]:
        env = {**self.env, **(env_extra or {})}
        return subprocess.run(
            [str(SCRIPT), *args],
            input=stdin,
            text=True,
            capture_output=True,
            env=env,
            timeout=5,
            check=False,
        )

    def test_script_is_executable(self) -> None:
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_selects_higher_remaining_backend(self) -> None:
        self._write_agy_quota(five_h=80, seven_d=90)
        snap = self._claude_snapshot(("ai0", [100.0, 64.0], None), ("ai1", [90.0, 52.0], None))
        res_ay = self.run_cli("--dry-run", "--json", env_extra={"CLAUDE_SNAPSHOT_JSON": snap})
        self.assertEqual(res_ay.returncode, 0, res_ay.stderr)
        data_ay = json.loads(res_ay.stdout)["data"]
        self.assertEqual(data_ay["selected"]["name"], "ay")
        self.assertIn("80% vs 64%", data_ay["selected"]["reason"])

        self._write_agy_quota(five_h=45, seven_d=70)
        snap2 = self._claude_snapshot(("ai0", [90.0, 55.0], None), ("ai2", [90.0, 75.0], None))
        res_claude = self.run_cli("--status", "--json", env_extra={"CLAUDE_SNAPSHOT_JSON": snap2})
        self.assertEqual(res_claude.returncode, 0, res_claude.stderr)
        data_claude = json.loads(res_claude.stdout)["data"]
        self.assertEqual(data_claude["selected"]["name"], "ai-round")
        self.assertEqual(data_claude["selected"]["detail"], "ai2 (2 slots)")
        self.assertIn("75% vs 45%", data_claude["selected"]["reason"])

    def test_ignores_ai_login_and_enforces_ai_round_20_pct_floor(self) -> None:
        # Even if ai-login is 100%, ai-round only uses numbered slots ai0+ and enforces >= 20%.
        self._write_agy_quota(five_h=30, seven_d=40)
        snap = self._claude_snapshot(
            ("ai-login", [100.0, 100.0], None),
            ("ai0", [18.0, 90.0], None),
            ("ai1", [50.0, 15.0], None),
        )
        res = self.run_cli(
            "--dry-run",
            "--json",
            "--min-remaining",
            "10",
            env_extra={"CLAUDE_SNAPSHOT_JSON": snap},
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)["data"]
        self.assertEqual(data["selected"]["name"], "ay")
        round_cand = next(c for c in data["candidates"] if c["name"] == "ai-round")
        self.assertFalse(round_cand["eligible"])
        self.assertEqual(round_cand["eligible_slots"], 0)
        self.assertIn("20% minimum", round_cand["unavailable"])

    def test_skips_low_quota_and_errors_when_both_below_threshold(self) -> None:
        self._write_agy_quota(five_h=5, seven_d=90)
        snap_ok = self._claude_snapshot(("ai1", [50.0, 40.0], None))
        res1 = self.run_cli("--dry-run", "--json", env_extra={"CLAUDE_SNAPSHOT_JSON": snap_ok})
        self.assertEqual(res1.returncode, 0, res1.stderr)
        self.assertEqual(json.loads(res1.stdout)["data"]["selected"]["name"], "ai-round")

        self._write_agy_quota(five_h=30, seven_d=35)
        snap_low = self._claude_snapshot(("ai0", [15.0, 90.0], None), ("ai1", [50.0, 19.0], None))
        res2 = self.run_cli("--dry-run", "--json", env_extra={"CLAUDE_SNAPSHOT_JSON": snap_low})
        self.assertEqual(res2.returncode, 0, res2.stderr)
        self.assertEqual(json.loads(res2.stdout)["data"]["selected"]["name"], "ay")

        self._write_agy_quota(five_h=5, seven_d=90)
        res3 = self.run_cli("--dry-run", "--json", env_extra={"CLAUDE_SNAPSHOT_JSON": snap_low})
        self.assertEqual(res3.returncode, 1)
        self.assertEqual(res3.stdout, "")
        err = json.loads(res3.stderr)
        self.assertFalse(err["ok"])
        self.assertEqual(err["error"]["code"], "NO_ELIGIBLE_BACKEND")

    def test_expired_agy_reset_bucket_is_ignored(self) -> None:
        self._write_agy_quota(
            five_h=2,
            seven_d=95,
            reset_5h=3600,
            reset_7d=86400,
            observed_at=self.now - 7200,
        )
        snap = self._claude_snapshot(("ai0", [100.0, 50.0], None))
        res = self.run_cli("--dry-run", "--json", env_extra={"CLAUDE_SNAPSHOT_JSON": snap})
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)["data"]
        ay_cand = next(c for c in data["candidates"] if c["name"] == "ay")
        self.assertTrue(ay_cand["eligible"])
        self.assertIsNone(ay_cand["remaining"]["5h"])
        self.assertEqual(ay_cand["remaining"]["7d"], 95.0)
        self.assertEqual(data["selected"]["name"], "ai-round")

    def test_missing_agy_cache_falls_back_gracefully(self) -> None:
        self.quota_file.unlink(missing_ok=True)
        snap_ok = self._claude_snapshot(("ai0", [80.0, 60.0], None))
        res1 = self.run_cli("--dry-run", "--json", env_extra={"CLAUDE_SNAPSHOT_JSON": snap_ok})
        self.assertEqual(res1.returncode, 0, res1.stderr)
        self.assertEqual(json.loads(res1.stdout)["data"]["selected"]["name"], "ai-round")

        res2 = self.run_cli("--dry-run", "--json", env_extra={"CLAUDE_SNAPSHOT_FAIL": "1"})
        self.assertEqual(res2.returncode, 0, res2.stderr)
        self.assertEqual(json.loads(res2.stdout)["data"]["selected"]["name"], "ay")

    def test_tie_breaking_uses_prefer_flag_and_env(self) -> None:
        self._write_agy_quota(five_h=80, seven_d=64)
        snap = self._claude_snapshot(("ai0", [80.0, 64.0], None))

        res_default = self.run_cli("--dry-run", "--json", env_extra={"CLAUDE_SNAPSHOT_JSON": snap})
        self.assertEqual(json.loads(res_default.stdout)["data"]["selected"]["name"], "ay")

        res_flag = self.run_cli(
            "--dry-run",
            "--json",
            "--prefer",
            "ai-round",
            env_extra={"CLAUDE_SNAPSHOT_JSON": snap},
        )
        self.assertEqual(json.loads(res_flag.stdout)["data"]["selected"]["name"], "ai-round")

        res_env = self.run_cli(
            "--dry-run",
            "--json",
            env_extra={"CLAUDE_SNAPSHOT_JSON": snap, "AI_AGENT_PREFER": "ai-round"},
        )
        self.assertEqual(json.loads(res_env.stdout)["data"]["selected"]["name"], "ai-round")

    def test_forced_backend_and_missing_binary(self) -> None:
        self._write_agy_quota(five_h=2, seven_d=2)
        snap = self._claude_snapshot(("ai0", [95.0, 95.0], None))
        res_force = self.run_cli(
            "--dry-run",
            "--json",
            "--backend",
            "ay",
            env_extra={"CLAUDE_SNAPSHOT_JSON": snap},
        )
        self.assertEqual(res_force.returncode, 0, res_force.stderr)
        self.assertEqual(json.loads(res_force.stdout)["data"]["selected"]["name"], "ay")

        res_missing = self.run_cli(
            "--dry-run",
            "--json",
            "--backend",
            "ai-round",
            env_extra={"AI_AGENT_AI_ROUND_BIN": str(self.root / "missing-bin")},
        )
        self.assertEqual(res_missing.returncode, 78)
        self.assertEqual(res_missing.stdout, "")
        self.assertEqual(json.loads(res_missing.stderr)["error"]["code"], "BACKEND_MISSING")

    def test_plain_help_version_and_usage_errors(self) -> None:
        self._write_agy_quota(five_h=90, seven_d=90)
        res_plain = self.run_cli("--dry-run", "--plain")
        self.assertEqual(res_plain.returncode, 0, res_plain.stderr)
        self.assertIn("selected\tay\t", res_plain.stdout)
        self.assertIn("candidate\tay\teligible\t90%\t90%\t", res_plain.stdout)

        res_help = self.run_cli("--help")
        self.assertEqual(res_help.returncode, 0, res_help.stderr)
        self.assertIn("Examples:", res_help.stdout)
        self.assertIn("Never selects OpenAI Codex", res_help.stdout)
        self.assertIn("ai-round", res_help.stdout)

        res_ver = self.run_cli("--version")
        self.assertEqual(res_ver.returncode, 0, res_ver.stderr)
        self.assertEqual(res_ver.stdout, "ai-agent 1.0.0\n")

        res_json_no_dry = self.run_cli("--json")
        self.assertEqual(res_json_no_dry.returncode, 2)
        self.assertEqual(res_json_no_dry.stdout, "")
        self.assertEqual(json.loads(res_json_no_dry.stderr)["error"]["code"], "INVALID_USAGE")

        res_unknown = self.run_cli("--bogus")
        self.assertEqual(res_unknown.returncode, 2)
        self.assertIn("Prefix backend options with `--`", res_unknown.stderr)

    def test_exec_replaces_process_preserves_tty_and_forwards_args(self) -> None:
        self._write_agy_quota(five_h=90, seven_d=90)
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        proc = subprocess.Popen(
            [str(SCRIPT), "-q", "--", "--resume", "abc"],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=self.env,
            start_new_session=True,
        )
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.assertEqual(proc.wait(timeout=5), 0)
        launch = json.loads(self.log.read_text(encoding="utf-8"))
        self.assertEqual(launch["backend"], "ay")
        self.assertEqual(launch["pid"], proc.pid)
        self.assertEqual(launch["pgrp"], proc.pid)
        self.assertEqual(launch["tty"], os.ttyname(slave))
        self.assertEqual(launch["args"], ["--resume", "abc"])

        # Non-TTY launch prints diagnostics to stderr and keeps stdout strictly backend data.
        self._write_agy_quota(five_h=20, seven_d=20)
        snap = self._claude_snapshot(("ai2", [90.0, 80.0], None))
        res_pipe = self.run_cli("--", "--model", "opus", env_extra={"CLAUDE_SNAPSHOT_JSON": snap})
        self.assertEqual(res_pipe.returncode, 0, res_pipe.stderr)
        self.assertIn("Starting ai-round (ai2)", res_pipe.stderr)
        self.assertEqual(
            json.loads(res_pipe.stdout),
            {"backend": "ai-round", "args": ["--model", "opus"]},
        )


if __name__ == "__main__":
    unittest.main()
