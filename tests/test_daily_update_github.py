"""Exercise GitHub bootstrap with real chezmoi and contained package installers."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "private_dot_config/my-scripts/daily_update"
BOOTSTRAP = ROOT / ".chezmoiscripts/run_once_after_install-github-tools.sh"
CHEZMOI = shutil.which("chezmoi")


class GitHubBootstrapTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.home = self.root / "home with spaces"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "python3").symlink_to(sys.executable)
        self.package = self.home / ".config/my-scripts/daily_update"
        shutil.copytree(PACKAGE, self.package)
        self.log = self.root / "commands"
        self.env = {
            "HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin",
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "TEST_ROOT": str(self.root), "TEST_LOG": str(self.log),
        }
        self.template = self.root / "gh-template"
        self.template.write_text('''#!/bin/bash
printf 'gh %s\\n' "$*" >>"$TEST_LOG"
case "$*" in
  'skill install --help') exit "${OLD_GH:-0}" ;;
  'extension list')
    [ "${FAIL_EXTENSION_LIST:-0}" = 0 ] || exit 7
    [ ! -f "$TEST_ROOT/extension" ] || cat "$TEST_ROOT/extension" ;;
  'extension install github/gh-stack')
    printf 'gh stack\\tgithub/gh-stack\\tv0.3.0\\n' >"$TEST_ROOT/extension" ;;
  'extension upgrade gh-stack') exit "${FAIL_STACK:-0}" ;;
  'skill install github/gh-stack gh-stack --agent codex --scope user --force')
    [ "${FAIL_CODEX_SKILL:-0}" = 0 ] || exit 7
    printf '%s\\n' "${SKILL_VERSION:-new}" >"$TEST_ROOT/codex-skill" ;;
  'skill install github/gh-stack gh-stack --agent claude-code --scope user --force')
    printf '%s\\n' "${SKILL_VERSION:-new}" >"$TEST_ROOT/claude-skill" ;;
  *) exit 9 ;;
esac
''')
        self.template.chmod(0o755)
        brew = self.bin / "brew"
        brew.write_text('''#!/bin/bash
printf 'brew %s\\n' "$*" >>"$TEST_LOG"
case "$*" in
  --prefix) printf '%s\\n' "$TEST_ROOT" ;;
  'list --formula --versions gh') printf 'gh 2.102.0\\n' ;;
  'install gh')
    [ "${FAIL_INSTALL:-0}" = 0 ] || exit 7
    cp "$TEST_ROOT/gh-template" "$TEST_ROOT/bin/gh" ;;
  'upgrade gh') exit "${FAIL_GH:-0}" ;;
  *) exit 9 ;;
esac
''')
        brew.chmod(0o755)

    def install(self, **extra):
        return subprocess.run(["bash", str(BOOTSTRAP)], cwd=self.root,
                              env=self.env | extra, text=True, capture_output=True)

    def logged(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_fresh_install_and_repeat_refresh_both_user_skills(self):
        for version in ("first", "second"):
            result = self.install(SKILL_VERSION=version)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for agent in ("codex", "claude"):
                self.assertEqual((self.root / f"{agent}-skill").read_text().strip(), version)
        self.assertEqual(self.logged().count("brew install gh\n"), 1)
        self.assertEqual(self.logged().count("gh extension install github/gh-stack\n"), 1)
        self.assertNotIn("extension upgrade", self.logged())

    def test_missing_homebrew_keeps_bootstrap_retryable(self):
        (self.bin / "brew").unlink()
        result = self.install()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("install Homebrew first", result.stdout)
        self.assertIn("retry chezmoi apply", result.stdout)
        self.assertFalse((self.bin / "gh").exists())

    def test_older_homebrew_cli_is_upgraded_before_skill_install(self):
        shutil.copy(self.template, self.bin / "gh")
        result = self.install(OLD_GH="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(self.logged().index("brew upgrade gh"),
                        self.logged().index("gh skill install github/gh-stack"))

    def test_failed_package_install_remains_retryable(self):
        result = self.install(FAIL_INSTALL="1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("installation failed", result.stdout)
        self.assertFalse((self.bin / "gh").exists())
        self.assertEqual(self.install().returncode, 0)

    def test_failed_extension_inventory_does_not_attempt_install(self):
        result = self.install(FAIL_EXTENSION_LIST="1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("extension install", self.logged())
        self.assertTrue((self.root / "claude-skill").exists())

    def test_conflicting_extension_is_preserved_and_skills_still_install(self):
        (self.root / "extension").write_text("gh stack\tother/gh-stack\t1.0\n")
        result = self.install()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("another source; preserved", result.stdout)
        self.assertNotIn("extension install", self.logged())
        self.assertNotIn("extension upgrade", self.logged())
        self.assertTrue((self.root / "claude-skill").exists())

    def test_bootstrap_honors_xdg_config_home(self):
        config = self.home / "custom config"
        config.mkdir()
        shutil.move(self.package.parent, config / "my-scripts")
        result = self.install(XDG_CONFIG_HOME=str(config))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(CHEZMOI, "chezmoi required")
    def test_chezmoi_deploys_package_and_retries_failed_run_once(self):
        source = self.root / "source"
        scripts = source / ".chezmoiscripts"
        scripts.mkdir(parents=True)
        shutil.copyfile(BOOTSTRAP, scripts / BOOTSTRAP.name)
        shutil.copytree(PACKAGE, source / "private_dot_config/my-scripts/daily_update")
        shutil.rmtree(self.package)
        command = [CHEZMOI, "--source", str(source), "--destination", str(self.home),
                   "--config", str(self.root / "chezmoi.toml"), "--persistent-state",
                   str(self.root / "state.boltdb"), "--no-tty", "apply"]
        for fail in ("1", "0"):
            result = subprocess.run(command, env=self.env | {"FAIL_CODEX_SKILL": fail},
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode == 0, fail == "0", result.stdout + result.stderr)
            self.assertTrue((self.root / "claude-skill").exists())
        self.log.unlink()
        result = subprocess.run(command, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.log.exists(), "successful run-once should not run again")


if __name__ == "__main__":
    unittest.main()
