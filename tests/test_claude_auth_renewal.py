"""Exercise cached renewal dates and real interactive shell startup with fake credentials."""

import datetime as dt
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "private_dot_config/my-scripts"
spec = importlib.util.spec_from_file_location("renewal", SCRIPTS / "claude_auth_renewal.py")
renewal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renewal)
NOW = dt.datetime(2026, 11, 5, 4, tzinfo=dt.timezone.utc).timestamp()
SECRET = "test-secret-must-never-appear"


class RenewalTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="claude-renewal-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.scripts = self.home / ".config/my-scripts"
        self.bin = self.scripts / "bin"
        self.bin.mkdir(parents=True)
        self.helper = self.bin / "claude-auth-renewal"
        shutil.copyfile(SCRIPTS / "bin/executable_claude-auth-renewal", self.helper)
        self.helper.chmod(0o755)
        shutil.copyfile(SCRIPTS / "claude_auth_renewal.py", self.scripts / "claude_auth_renewal.py")
        self.cache = self.home / ".cache/claude-auth-renewal"
        self.env = {**os.environ, "HOME": str(self.home), "PATH": f"{self.bin}:{os.environ['PATH']}",
                    "XDG_CONFIG_HOME": str(self.home / ".config"),
                    "XDG_CACHE_HOME": str(self.home / ".cache"),
                    "XDG_STATE_HOME": str(self.home / ".local/state"), "TERM": "dumb"}
        for name in ("CLAUDE_CONFIG_DIR", "CLAUDE_ACCOUNTS_DIR", "BASH_ENV", "ENV", "BASH_FULL_INIT"):
            self.env.pop(name, None)

    def credentials(self, name=".claude", latest=NOW + 4 * renewal.DAY, **changes):
        config = self.home / name
        config.mkdir(parents=True, exist_ok=True)
        oauth = {"refreshToken": SECRET, "accessToken": SECRET,
                 "expiresAt": (NOW + 3600) * 1000, "refreshTokenExpiresAt": latest * 1000}
        oauth.update(changes)
        (config / ".credentials.json").write_text(json.dumps({"claudeAiOauth": oauth}))
        return config

    def run_helper(self, *args):
        result = subprocess.run([str(self.helper), *args], env=self.env, capture_output=True,
                                text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        return result.stdout

    def cached(self, message="Claude: test account expires soon; claude auth login", age=0):
        self.cache.mkdir(parents=True, exist_ok=True)
        (self.cache / "notice").write_text(f"{int(time.time()) - age}\n{message}\n")

    def test_three_day_window_matches_claude_warning(self):
        message = renewal.login_notice(self.credentials(), self.home, NOW)
        self.assertIn("2026-11-06–2026-11-09 UTC", message)
        self.assertIn("renew before 2026-11-06: claude auth login", message)
        self.assertNotIn(SECRET, message)

    def test_warning_starts_seven_days_before_earliest(self):
        config = self.credentials(latest=NOW + 10 * renewal.DAY)
        self.assertIsNotNone(renewal.login_notice(config, self.home, NOW))
        self.credentials(latest=NOW + 10 * renewal.DAY + 1)
        self.assertIsNone(renewal.login_notice(config, self.home, NOW))

    def test_inside_window_and_past_latest(self):
        config = self.credentials(latest=NOW + 2 * renewal.DAY)
        self.assertIn("can expire now", renewal.login_notice(config, self.home, NOW))
        self.credentials(latest=NOW - 1)
        self.assertIn("may have expired", renewal.login_notice(config, self.home, NOW))

    def test_access_token_expiry_is_never_used_as_login_expiry(self):
        for invalid in (None, True, "tomorrow", float("nan"), -1):
            config = self.credentials(refreshTokenExpiresAt=invalid)
            self.assertIn("renewal date unknown", renewal.login_notice(config, self.home, NOW))
        self.credentials(expiresAt=(NOW + 20 * renewal.DAY) * 1000)
        self.assertIn("conflicting expiry", renewal.login_notice(config, self.home, NOW))

    def test_other_config_and_identity_are_distinct_and_terminal_safe(self):
        config = self.credentials(".claude-work")
        (config / ".claude.json").write_text(json.dumps({"oauthAccount": {"emailAddress": "work@example.invalid\n\u001b"}}))
        message = renewal.login_notice(config, self.home, NOW)
        self.assertIn("work@example.invalid", message)
        self.assertIn(f"CLAUDE_CONFIG_DIR={config} claude auth login", message)
        self.assertNotIn("\n", message)
        self.assertNotIn("\x1b", message)
        with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}, clear=True):
            self.assertEqual(renewal.config_dirs(self.home), [self.home / ".claude", config])

    def test_unreadable_metadata_is_reported_without_its_contents(self):
        config = self.credentials()
        (config / ".credentials.json").write_text(SECRET)
        message = renewal.login_notice(config, self.home, NOW)
        self.assertIn("cannot read renewal metadata", message)
        self.assertNotIn(SECRET, message)

    def test_setup_token_is_estimated_and_uses_the_slot_renewal_command(self):
        directory = self.home / "tokens"
        directory.mkdir()
        (directory / "2.json").write_text(json.dumps({"token": SECRET, "label": "work",
                                                      "added": "2025-11-10"}))
        message, = renewal.token_notices(directory, NOW)
        self.assertIn("estimated expiry 2026-11-10", message)
        self.assertIn("claude-account add 2", message)
        self.assertNotIn(SECRET, message)

    def test_refresh_aggregates_accounts_and_writes_no_secrets(self):
        self.credentials(latest=time.time() + 4 * renewal.DAY)
        self.credentials(".claude-work", latest=time.time() + 5 * renewal.DAY)
        self.assertEqual(self.run_helper("--refresh"), "")
        cache = (self.cache / "notice").read_text()
        self.assertEqual(cache.count("claude auth login"), 2)
        self.assertNotIn(SECRET, cache)
        self.assertEqual((self.cache / "notice").stat().st_mode & 0o777, 0o600)

    def test_fresh_cache_never_invokes_python_or_claude(self):
        self.cached("")
        for command in ("python3", "claude"):
            stub = self.bin / command
            stub.write_text(f'#!/bin/sh\ntouch "{self.home}/unexpected-call"\nexit 1\n')
            stub.chmod(0o755)
        self.assertEqual(self.run_helper(), "")
        self.assertFalse((self.home / "unexpected-call").exists())

    def test_missing_cache_refreshes_in_background_for_next_shell(self):
        self.credentials(latest=time.time() + 4 * renewal.DAY)
        self.assertEqual(self.run_helper(), "")
        deadline = time.monotonic() + 3
        while not (self.cache / "notice").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIn("claude auth login", self.run_helper())
        self.assertEqual(self.run_helper(), "")

    def test_once_per_day_even_for_concurrent_panes(self):
        self.cached()
        children = [subprocess.Popen([str(self.helper)], env=self.env, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True) for _ in range(12)]
        results = [child.communicate(timeout=5) for child in children]
        self.assertEqual(sum(out.count("Claude:") for out, err in results), 1)
        self.assertTrue(all(not err for out, err in results))
        (self.cache / "seen").write_text("2000-01-01\n")
        self.assertIn("Claude:", self.run_helper())

    def prepare_shells(self):
        shutil.copyfile(ROOT / "dot_bash_profile", self.home / ".bash_profile")
        shutil.copyfile(ROOT / "dot_bashrc", self.home / ".bashrc")
        (self.home / ".cargo").mkdir()
        (self.home / ".cargo/env").write_text("")
        (self.scripts / "shell").mkdir()
        shutil.copyfile(SCRIPTS / "shell/productivity.sh", self.scripts / "shell/productivity.sh")
        shutil.copytree(ROOT / "private_dot_config/nushell", self.home / ".config/nushell")
        # Disable unrelated interactive tools, leaving both real startup files intact.
        for command in ("starship", "atuin", "daily-update", "direnv", "fastfetch"):
            stub = self.bin / command
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)

    def interactive(self, args):
        master, slave = pty.openpty()
        try:
            child = subprocess.Popen(args, stdin=slave, stdout=slave, stderr=slave,
                                     env=self.env, cwd=self.home, start_new_session=True,
                                     preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0))
            os.close(slave)
            slave = None
            is_nu = Path(args[0]).name == "nu"
            if not is_nu:
                os.write(master, b"exit\n")
            output = bytearray()
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output.extend(chunk)
                    if b"\x1b[6n" in chunk:
                        os.write(master, b"\x1b[1;1Rexit\r")
                elif child.poll() is not None:
                    break
            if child.poll() is None:
                child.kill()
            self.assertEqual(child.wait(timeout=2), 0, output.decode(errors="replace"))
            return output.decode(errors="replace")
        finally:
            os.close(master)
            if slave is not None:
                os.close(slave)

    @unittest.skipUnless(shutil.which("nu"), "Nushell required")
    def test_real_interactive_bash_login_and_nu_share_daily_gate(self):
        self.prepare_shells()
        self.cached()
        self.assertIn("Claude: test account", self.interactive(["/usr/bin/bash", "-il"]))
        self.assertNotIn("Claude: test account", self.interactive([shutil.which("nu")]))
        (self.cache / "seen").unlink()
        self.assertIn("Claude: test account", self.interactive([shutil.which("nu")]))

    @unittest.skipUnless(shutil.which("nu"), "Nushell required")
    def test_noninteractive_shells_are_silent_and_do_not_refresh(self):
        self.prepare_shells()
        self.cached(age=7200)
        before = (self.cache / "notice").read_bytes()
        for args, expected in ((["/usr/bin/bash", "-c", "true"], b""),
                               (["/usr/bin/bash", "-lc", "true"], b""),
                               ([shutil.which("nu"), "-c", "true | ignore"], b""),
                               ([shutil.which("nu"), "-c", "true"], b"true\n")):
            result = subprocess.run(args, env=self.env, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, expected)
            self.assertEqual(result.stderr, b"")
        self.assertFalse((self.cache / "seen").exists())
        self.assertEqual((self.cache / "notice").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
