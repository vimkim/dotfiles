"""Check portable skill inventories through the CLI and disposable home directories."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "private_dot_config/my-scripts/bin/executable_my-skill-check"


class MySkillCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "home with spaces"
        self.home.mkdir()
        self.env = {**os.environ, "HOME": str(self.home),
                    "XDG_CONFIG_HOME": str(self.home / "configuration"),
                    "CLAUDE_CONFIG_DIR": str(self.home / "claude configuration"),
                    "CODEX_HOME": str(self.home / "codex configuration")}
        self.roots = {"shared": self.home / ".agents/skills",
                      "claude": Path(self.env["CLAUDE_CONFIG_DIR"]) / "skills",
                      "codex": Path(self.env["CODEX_HOME"]) / "skills"}
        self.manifest = Path(self.env["XDG_CONFIG_HOME"]) / "my-scripts/skills.json"

    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, str(SOURCE), *map(str, args)],
                              env=self.env if env is None else env, cwd=self.home,
                              text=True, capture_output=True, timeout=10)

    def save_manifest(self, **skills):
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        self.manifest.write_text(json.dumps({"version": 1, "skills": {
            location: skills.get(location, []) for location in self.roots
        }}), encoding="utf-8")

    def install(self, location, name):
        directory = self.roots[location] / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text("# A user skill\n", encoding="utf-8")
        return directory

    def link(self, location, name, target):
        self.roots[location].mkdir(parents=True, exist_ok=True)
        path = self.roots[location] / name
        path.symlink_to(target, target_is_directory=True)
        return path

    def test_capture_includes_lockless_skills_and_preserves_locations(self):
        shared = self.install("shared", "personal-skill")
        self.link("claude", "personal-skill", shared)
        self.install("shared", "gh-stack")
        self.install("claude", "gh-stack")
        self.install("codex", "local-helper")
        for location, name in (("shared", ".trash/old"), ("claude", "synced/id/nested"),
                               ("codex", ".system/bundled"), ("shared", "container/nested")):
            self.install(location, name)
        result = self.run_cli("--capture")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), {"version": 1, "skills": {
            "shared": ["gh-stack", "personal-skill"],
            "claude": ["gh-stack", "personal-skill"], "codex": ["local-helper"]}})
        self.assertEqual(result.stdout, self.run_cli("--capture").stdout)
        self.assertFalse(self.manifest.exists())
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text(result.stdout, encoding="utf-8")
        check = self.run_cli()
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(check.stdout, "Matched 3 skills in 5 locations.\n")
        self.assertEqual(self.manifest.read_text(), result.stdout)
        self.assertTrue((shared / "SKILL.md").is_file())

    def test_missing_extra_and_broken_are_grouped_without_duplicates(self):
        self.save_manifest(shared=["absent", "kept"], claude=["absent", "broken"])
        self.install("shared", "kept")
        self.install("shared", "extra")
        self.install("codex", "extra")
        link = self.link("claude", "broken", self.home / "missing")
        original = self.manifest.read_bytes()
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "Missing: absent [shared, claude]", "Extra: extra [shared, codex]",
            "Broken: broken [claude] (missing symlink target or entry disappeared during scan)",
            "2 missing, 2 extra, 1 broken locations."])
        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertTrue(link.is_symlink())
        self.assertTrue((self.roots["codex"] / "extra/SKILL.md").is_file())

    def test_lost_claude_link_is_missing_even_if_shared_skill_survives(self):
        self.save_manifest(shared=["same"], claude=["same"])
        self.install("shared", "same")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Missing: same [claude]", result.stdout)
        self.assertNotIn("Extra:", result.stdout)

    def test_broken_entries_abort_capture_without_partial_json(self):
        self.install("shared", "valid")
        self.link("claude", "dangling", self.home / "missing")
        self.link("claude", "loop", self.roots["claude"] / "loop")
        plain_file = self.home / "plain-file"
        plain_file.touch()
        self.link("claude", "not-a-directory", plain_file / "missing")
        directory = self.roots["codex"] / "bad-file"
        (directory / "SKILL.md").mkdir(parents=True)
        missing_file = self.roots["codex"] / "dangling-file"
        missing_file.mkdir()
        (missing_file / "SKILL.md").symlink_to(self.home / "missing-file")
        result = self.run_cli("--capture")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("symlink loop", result.stderr)
        self.assertIn("SKILL.md is not a regular file", result.stderr)
        self.assertIn("SKILL.md has a missing symlink target", result.stderr)
        self.assertIn("capture aborted", result.stderr)
        self.assertFalse(self.manifest.exists())

    def test_expected_invalid_skill_directory_is_broken(self):
        self.save_manifest(shared=["no-skill-file", "plain-file"])
        (self.roots["shared"] / "no-skill-file").mkdir(parents=True)
        (self.roots["shared"] / "plain-file").touch()
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Broken: no-skill-file [shared] (SKILL.md is missing)", result.stdout)
        self.assertIn("Broken: plain-file [shared] (entry is not a directory)", result.stdout)
        self.assertIn("0 missing, 0 extra, 2 broken locations.", result.stdout)

    def test_manifest_override_and_empty_environment_fallbacks(self):
        self.install("shared", "required")
        self.save_manifest(shared=["required"])
        alternate = self.home / "alternate.json"
        self.manifest.rename(alternate)
        for value in ("", "relative-config"):
            with self.subTest(xdg=value):
                env = {**self.env, "XDG_CONFIG_HOME": value, "CLAUDE_CONFIG_DIR": "", "CODEX_HOME": ""}
                fallback = self.home / ".config/my-scripts/skills.json"
                fallback.parent.mkdir(parents=True, exist_ok=True)
                fallback.write_text(alternate.read_text())
                self.assertEqual(self.run_cli(env=env).returncode, 0)
                self.assertEqual(self.run_cli("--manifest", alternate, env=env).returncode, 0)
        self.assertFalse(self.manifest.exists())

    def test_missing_roots_are_empty_but_invalid_roots_are_errors(self):
        self.save_manifest(shared=["required"])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Missing: required [shared]", result.stdout)
        self.roots["shared"].parent.mkdir(parents=True)
        self.roots["shared"].touch()
        result = self.run_cli("--capture")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.roots["shared"].unlink()
        self.roots["shared"].symlink_to(self.home / "missing-root")
        result = self.run_cli("--capture")
        self.assertEqual(result.returncode, 2)
        self.assertIn("skill root has a missing symlink target", result.stderr)

    def test_missing_and_invalid_manifests_are_errors(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn(str(self.manifest), result.stderr)
        self.assertEqual(result.stdout, "")
        self.save_manifest()
        valid = json.loads(self.manifest.read_text())
        invalid = ["{", "[]", json.dumps({**valid, "version": True}),
                   json.dumps({**valid, "version": 2}), json.dumps({**valid, "extra": []}),
                   json.dumps({"version": 1, "skills": {"shared": []}})]
        for names in (["duplicate", "duplicate"], ["../escape"], [".hidden"], [""],
                      [42], ["synced"], ["has\\separator"], ["has\nnewline"], "not-a-list"):
            invalid.append(json.dumps({"version": 1, "skills": {
                "shared": names, "claude": [], "codex": []}}))
        for document in invalid:
            with self.subTest(document=document):
                self.manifest.write_text(document)
                result = self.run_cli()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("my-skill-check:", result.stderr)
                self.assertEqual(self.manifest.read_text(), document)

    @unittest.skipIf(os.geteuid() == 0, "root bypasses file permissions")
    def test_unreadable_root_or_skill_is_an_error(self):
        directory = self.install("shared", "secret")
        skill = directory / "SKILL.md"
        self.save_manifest(shared=["secret"])
        for path in (self.roots["shared"], skill):
            with self.subTest(path=path):
                mode = path.stat().st_mode
                try:
                    path.chmod(0)
                    for args in ((), ("--capture",)):
                        result = self.run_cli(*args)
                        self.assertEqual(result.returncode, 2)
                        self.assertEqual(result.stdout, "")
                        self.assertIn("Permission denied", result.stderr)
                finally:
                    path.chmod(mode)


if __name__ == "__main__":
    unittest.main()
