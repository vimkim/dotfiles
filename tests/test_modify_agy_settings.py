"""Verify chezmoi modify_ script for Antigravity CLI settings."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGY_MODIFY = ROOT / "dot_gemini/antigravity-cli/modify_private_settings.json"
CHEZMOI = shutil.which("chezmoi")

EXPECTED_TEMPLATES = [
    ".claude/CLAUDE.md",
    ".codex/hooks.json",
    ".config/nushell/autoload/deeptutor.nu",
    ".gemini/AGENTS.md",
    ".gemini/config/skills.json",
    ".profile",
    ".zshenv",
]


def run_script(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(AGY_MODIFY)],
        input=stdin,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )


class AgyModifySettingsTest(unittest.TestCase):
    def test_script_is_executable_without_tmpl_suffix(self) -> None:
        self.assertTrue(os.access(AGY_MODIFY, os.X_OK))
        self.assertFalse(AGY_MODIFY.name.endswith(".tmpl"))

    def test_fresh_install_outputs_shared_defaults_only(self) -> None:
        res = run_script("")
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(data["agentMode"], "")
        self.assertEqual(data["altScreenMode"], "always")
        self.assertEqual(data["effort"], "high")
        self.assertIs(data["enableTerminalSandbox"], False)
        self.assertEqual(data["model"], "Orchestrator (Neon)")
        self.assertEqual(data["toolPermission"], "always-proceed")
        self.assertEqual(
            list(data["statusLine"].items()),
            [("type", "command"), ("command", "~/.gemini/antigravity-cli/statusline.sh")],
        )
        self.assertNotIn("trustedWorkspaces", data)
        self.assertNotIn("/home/vimkim", res.stdout)

    def test_matching_shared_keys_preserve_input_verbatim(self) -> None:
        existing = (
            "{\n"
            '  "trustedWorkspaces": ["/tmp/proj-a", "/tmp/proj-b"],\n'
            '  "gcp": {"project": "my-proj", "location": "global"},\n'
            '  "agentMode": "",\n'
            '  "altScreenMode": "always",\n'
            '  "effort": "high",\n'
            '  "enableTerminalSandbox": false,\n'
            '  "model": "Orchestrator (Neon)",\n'
            '  "statusLine": {\n'
            '    "type": "command",\n'
            '    "command": "~/.gemini/antigravity-cli/statusline.sh"\n'
            "  },\n"
            '  "toolPermission": "always-proceed"\n'
            "}\n"
        )
        res = run_script(existing)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout, existing)

    def test_stale_or_missing_shared_key_merges_and_keeps_local_keys(self) -> None:
        existing = json.dumps(
            {
                "effort": "low",
                "trustedWorkspaces": ["/tmp/ws1"],
                "gcp": {"project": "p1", "location": "us"},
            },
            indent=2,
        )
        res = run_script(existing)
        self.assertEqual(res.returncode, 0, res.stderr)
        merged = json.loads(res.stdout)
        self.assertEqual(merged["agentMode"], "")
        self.assertEqual(merged["effort"], "high")
        self.assertIs(merged["enableTerminalSandbox"], False)
        self.assertEqual(merged["model"], "Orchestrator (Neon)")
        self.assertEqual(merged["trustedWorkspaces"], ["/tmp/ws1"])
        self.assertEqual(merged["gcp"], {"project": "p1", "location": "us"})
        self.assertEqual(list(merged["statusLine"].keys()), ["type", "command"])

    def test_invalid_or_non_object_json_fails(self) -> None:
        for bad in ("{broken json", "[]", '"scalar"'):
            with self.subTest(bad=bad):
                res = run_script(bad)
                self.assertNotEqual(res.returncode, 0)
                self.assertEqual(res.stdout, "")
                self.assertTrue(res.stderr.strip())


@unittest.skipUnless(CHEZMOI, "chezmoi required")
class ChezmoiModifyAgyIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="chezmoi-modify-agy-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        self.config = self.root / "chezmoi.json"
        self.config.write_text(
            json.dumps(
                {
                    "destDir": str(self.destination),
                    "persistentState": str(self.root / "state.boltdb"),
                    "cacheDir": str(self.root / "cache"),
                }
            )
        )
        self.base = [CHEZMOI, "--source", str(self.source), "--config", str(self.config)]

        agy_dst = self.source / "dot_gemini/antigravity-cli/modify_private_settings.json"
        agy_dst.parent.mkdir(parents=True)
        shutil.copy2(AGY_MODIFY, agy_dst)

        self.agy_src = agy_dst
        self.agy_target = self.destination / ".gemini/antigravity-cli/settings.json"

    def run_chezmoi(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*self.base, *args],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def test_apply_local_mutations_stay_clean_and_shared_updates_merge(self) -> None:
        apply_res = self.run_chezmoi("apply", "--no-tty")
        self.assertEqual(apply_res.returncode, 0, apply_res.stderr)

        self.assertEqual(self.agy_target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.run_chezmoi("status").stdout, "")
        self.assertEqual(self.run_chezmoi("diff").stdout, "")

        # Simulate agy appending trustedWorkspaces on disk.
        agy_data = json.loads(self.agy_target.read_text(encoding="utf-8"))
        agy_data["trustedWorkspaces"] = ["/tmp/ws-alpha", "/tmp/ws-beta"]
        self.agy_target.write_text(json.dumps(agy_data, indent=2) + "\n", encoding="utf-8")

        self.assertEqual(self.run_chezmoi("status").stdout, "")
        self.assertEqual(self.run_chezmoi("diff").stdout, "")

        # Update one shared key in the modify_ script; local entries must survive diff & apply.
        self.agy_src.write_text(
            self.agy_src.read_text(encoding="utf-8").replace('"effort": "high"', '"effort": "max"'),
            encoding="utf-8",
        )

        diff_res = self.run_chezmoi("diff")
        self.assertEqual(diff_res.returncode, 0, diff_res.stderr)
        self.assertIn('"effort": "max"', diff_res.stdout)
        self.assertNotIn('"trustedWorkspaces"', diff_res.stdout)

        reapply = self.run_chezmoi("apply", "--no-tty")
        self.assertEqual(reapply.returncode, 0, reapply.stderr)

        new_agy = json.loads(self.agy_target.read_text(encoding="utf-8"))
        self.assertEqual(new_agy["effort"], "max")
        self.assertEqual(new_agy["trustedWorkspaces"], ["/tmp/ws-alpha", "/tmp/ws-beta"])
        self.assertEqual(self.run_chezmoi("status").stdout, "")
        self.assertEqual(self.run_chezmoi("diff").stdout, "")

    def test_repo_scripts_and_templates_classification(self) -> None:
        scripts = subprocess.run(
            [CHEZMOI, "--source", str(ROOT), "managed", "--include=scripts"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        self.assertNotIn(".gemini/antigravity-cli/settings.json", scripts)

        templates = subprocess.run(
            [CHEZMOI, "--source", str(ROOT), "managed", "--include=templates"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        self.assertEqual(templates, EXPECTED_TEMPLATES)


if __name__ == "__main__":
    unittest.main()
