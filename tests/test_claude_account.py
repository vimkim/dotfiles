"""Exercise claude-account slots and shortcuts without a real Claude login."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import http.client
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import urllib.error


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "private_dot_config/my-scripts/bin"
SCRIPT = BIN / "executable_claude-account"
STATUSLINE = ROOT / "dot_claude/executable_statusline.sh"
TOKEN = "sk-ant-oat01-test-secret"
# Records how it was called so tests can see argv and the token Claude would receive.
STUB = f"""#!{sys.executable}
import json, os, sys
with open(os.environ["STUB_LOG"], "a") as handle:
    handle.write(json.dumps({{"name": os.path.basename(sys.argv[0]), "args": sys.argv[1:],
                              "token": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"),
                              "api": os.environ.get("ANTHROPIC_API_KEY"),
                              "auth": os.environ.get("ANTHROPIC_AUTH_TOKEN")}}) + "\\n")
"""


class ClaudeAccountTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="claude-account-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "log.jsonl"
        self.accounts = self.root / "state/claude-accounts"
        self.config = self.root / "config dir"
        (self.bin / "claude").write_text(STUB)
        (self.bin / "claude").chmod(0o755)
        for name in ("claude-account", "ai-best", "herdr-new-tab-ai-best"):
            shutil.copyfile(BIN / f"executable_{name}", self.bin / name)
            (self.bin / name).chmod(0o755)
        (self.bin / "herdr-new-workspace-ai-best").symlink_to("herdr-new-tab-ai-best")
        for source in SCRIPT.parent.glob("symlink_ai*"):
            (self.bin / source.name.removeprefix("symlink_")).symlink_to(source.read_text().strip())
        self.env = {**os.environ, "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                    "STUB_LOG": str(self.log), "XDG_STATE_HOME": str(self.root / "state"),
                    "CLAUDE_CONFIG_DIR": str(self.config)}
        for name in ("CLAUDE_ACCOUNTS_DIR", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            self.env.pop(name, None)

    def account(self, *args, stdin="", command="claude-account"):
        return subprocess.run([str(self.bin / command), *args], env=self.env,
                              input=stdin, capture_output=True, text=True, timeout=10)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def add_slot(self, slot, *extra):
        result = self.account("add", str(slot), "--paste", *extra, stdin=TOKEN + "\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_login_drops_inherited_credentials(self):
        self.env["CLAUDE_CODE_OAUTH_TOKEN"] = "inherited-from-ai2"
        self.env["ANTHROPIC_API_KEY"] = "inherited-api"
        self.env["ANTHROPIC_AUTH_TOKEN"] = "inherited-auth"
        self.accounts.mkdir(parents=True)
        (self.accounts / "0.json").write_text(json.dumps({"token": TOKEN}))
        result = self.account("run", "login", "-c", "two words")
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = str(self.config / "local-settings.json")
        self.assertEqual(self.calls(), [{"name": "claude", "token": None, "api": None, "auth": None, "args": [
            "--settings", settings, "--dangerously-skip-permissions", "-c", "two words"]}])

    def test_settings_fall_back_to_home_claude_when_config_dir_is_empty(self):
        self.env["CLAUDE_CONFIG_DIR"] = ""
        self.env["HOME"] = str(self.root / "home")
        with (self.bin / "claude").open("a") as stub:
            stub.write('assert "CLAUDE_CONFIG_DIR" not in os.environ\n')
        self.assertEqual(self.account("run").returncode, 0)
        self.assertEqual(self.calls()[0]["args"][1],
                         str(self.root / "home/.claude/local-settings.json"))

    def test_added_slot_passes_its_token_and_stays_private(self):
        self.add_slot(2, "--label", "personal")
        stored = self.accounts / "3.json"
        self.assertEqual(stored.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.accounts.stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads(stored.read_text())["token"], TOKEN)
        self.assertEqual(self.account("run", "2", "--resume").returncode, 0)
        call = self.calls()[0]
        self.assertEqual(call["token"], TOKEN)
        self.assertEqual(call["args"][-1], "--resume")

    def test_missing_slot_fails_before_launching_claude(self):
        result = self.account("run", "3")
        self.assertEqual(result.returncode, 1)
        self.assertIn("claude-account add 3", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_add_runs_setup_token_without_an_inherited_token(self):
        self.env["CLAUDE_CODE_OAUTH_TOKEN"] = "inherited"
        self.env["ANTHROPIC_API_KEY"] = "inherited"
        self.env["ANTHROPIC_AUTH_TOKEN"] = "inherited"
        result = self.account("add", "2", stdin=TOKEN + "\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [{"name": "claude", "args": ["setup-token"], "token": None, "api": None, "auth": None}])

    def test_rejects_bad_slots_and_tokens(self):
        for args in (("add", "login", "--paste"), ("remove", "login"), ("add", "x", "--paste"), ("add", "2", "--bogus")):
            with self.subTest(args=args):
                self.assertEqual(self.account(*args).returncode, 2)
        self.assertEqual(self.account("add", "2", "--paste", stdin="two words\n").returncode, 1)
        self.assertFalse((self.accounts / "3.json").exists())

    def test_list_shows_slots_without_tokens_and_remove_deletes(self):
        self.add_slot(0, "--label", "personal")
        listing = self.account("list")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn("ai-login  /login", listing.stdout)
        self.assertIn("ai1  not configured", listing.stdout)
        self.assertIn("ai0  token", listing.stdout)
        self.assertIn("personal", listing.stdout)
        self.assertNotIn(TOKEN, listing.stdout)
        self.assertEqual(self.account("remove", "0").returncode, 0)
        self.assertEqual(self.account("run", "0").returncode, 1)

    def test_status_reports_token_without_running_claude(self):
        self.add_slot(2, "--username", "team@example.test")
        result = self.account("status", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("team@example.test [declared, unverified]", result.stdout)
        self.assertIn("configured; unverified", result.stdout)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        self.assertEqual(self.calls(), [])

    def test_inventory_isolates_bad_files_and_preserves_credentials(self):
        self.add_slot(2, "--label", "team\nname", "--username", "team@example.test")
        (self.accounts / "1.json").write_text("{broken")
        (self.accounts / "0.json").write_text(json.dumps({"token": TOKEN}))
        (self.accounts / "5.json").write_text(json.dumps({"token": TOKEN, "added": "bad"}))
        paths = list(self.accounts.iterdir())
        before = {p: hashlib.sha256(p.read_bytes()).digest() for p in paths}
        result = self.account("status", "--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        for value in ("ai-login", "ai0", "ai1", "ai2", "ai4", "unreadable or invalid", "team\\u000aname"):
            self.assertIn(value, result.stdout)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).digest() for p in paths})
        self.assertIn("renewal estimate unavailable", self.account("list").stdout)
        self.assertEqual(self.calls(), [])

    def test_label_preserves_existing_data_and_private_mode(self):
        self.add_slot(2, "--label", "team")
        path = self.accounts / "3.json"
        existing = json.loads(path.read_text())
        existing["extra"] = {"keep": True}
        path.write_text(json.dumps(existing))
        result = self.account("label", "2", "--username", "team@example.test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.read_text()), {**existing, "username": "team@example.test"})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.account("label", "login", "--label", "x").returncode, 2)
        self.assertEqual(self.account("status", "2", "--all").returncode, 2)
        self.assertEqual(self.account("list", "extra").returncode, 2)

    def test_missing_and_malformed_slot_one_never_launch(self):
        self.assertEqual(self.account("run", "1").returncode, 1)
        self.accounts.mkdir(parents=True)
        (self.accounts / "2.json").write_text("not json")
        self.assertEqual(self.account("run", "1").returncode, 1)
        (self.accounts / "2.json").write_text(json.dumps({"token": "bad\x00token"}))
        self.assertEqual(self.account("run", "1").returncode, 1)
        self.assertEqual(self.calls(), [])

    def test_bash_redirected_startup_puts_ai_on_path(self):
        home = self.root / "home"
        helpers = home / ".config/my-scripts/bin"
        helpers.parent.mkdir(parents=True)
        helpers.symlink_to(self.bin, target_is_directory=True)
        env = {**self.env, "HOME": str(home), "PROMPT_COMMAND": "sentinel"}
        env["PATH"] = os.pathsep.join(path for path in os.get_exec_path(env) if path != str(self.bin))
        for name in ("BASH_ENV", "BASH_FULL_INIT", "BASH_IT"):
            env.pop(name, None)
        result = subprocess.run(
            ["bash", "--rcfile", str(ROOT / "dot_bashrc"), "-ic",
             '[[ $(type -t ai) == file && ! -v BASH_IT && $PROMPT_COMMAND == sentinel ]] && ai "two words"'],
            env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[0]["args"][-1], "two words")

    def test_executable_shortcuts_forward_arguments_and_select_account(self):
        self.env["CLAUDE_CODE_OAUTH_TOKEN"] = "inherited"
        self.accounts.mkdir(parents=True)
        for slot in range(1, 11):
            (self.accounts / f"{slot}.json").write_text(json.dumps({"token": f"{TOKEN}-{slot}"}))
        settings = ["--settings", str(self.config / "local-settings.json"), "--dangerously-skip-permissions"]
        args = ["123", "two words", "", "--resume"]
        for name, slot in [("ai", 0), ("ai-login", 0), *((f"ai{slot - 1}", slot) for slot in range(1, 11))]:
            with self.subTest(name=name):
                result = self.account(*args, command=name)
                self.assertEqual(result.returncode, 0, result.stderr)
                call = self.calls()[-1]
                self.assertEqual(call["token"], f"{TOKEN}-{slot}" if slot else None)
                self.assertEqual(call["args"], [*settings, *args])
        result = self.account("-c", command="aip")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[-1]["args"], [*settings, "read prompt.md and execute", "-c"])
        self.assertIsNone(self.calls()[-1]["token"])

    def test_status_shortcut_reports_all_accounts(self):
        self.add_slot(2)
        result = self.account(command="ai-status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.account("status", "--all").stdout)
        self.assertIn("ai2", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_larger_slot_uses_the_full_launch_command(self):
        result = self.account("add", "10", "--paste", stdin=TOKEN + "\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("claude-account run 10", result.stdout)
        self.assertEqual(self.account("run", "10").returncode, 0)
        self.assertEqual(self.calls()[0]["token"], TOKEN)

    def prepare_accounts(self, slots):
        self.env.update(HOME=str(self.root), HERDR_ENV="0")
        for slot in slots:
            result = self.account("add", str(slot), "--paste", stdin=f"{TOKEN}-{slot}\n")
            self.assertEqual(result.returncode, 0, result.stderr)

    @staticmethod
    def usage_input(five_hour, weekly, reset=None):
        if reset is None:
            reset = int(time.time()) + 600
        return json.dumps({"rate_limits": {
            "five_hour": {"used_percentage": 100 - five_hour, "resets_at": reset},
            "seven_day": {"used_percentage": 100 - weekly, "resets_at": reset},
        }})

    def observe(self, slot, five_hour, weekly, *, reset=None):
        with mock.patch.dict(self.env, {"CLAUDE_CODE_OAUTH_TOKEN": f"{TOKEN}-{slot}"}):
            result = self.account("observe", stdin=self.usage_input(five_hour, weekly, reset))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_best_help_and_version_without_account_access(self):
        (self.bin / "claude-account").write_text("#!/bin/sh\nexit 99\n")
        self.env["HERDR_ENV"] = "0"
        help_result = self.account("--help", command="ai-best")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        for value in ("current terminal", "5-hour", "7-day", "10%", "unknown", "herdr-new-tab-ai-best"):
            self.assertIn(value, help_result.stdout)
        version = self.account("--version", command="ai-best")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertRegex(version.stdout, r"^ai-best [0-9]+\.[0-9]+\.[0-9]+\n$")
        invalid = self.account("--bogus", command="ai-best")
        self.assertEqual(invalid.returncode, 2, invalid.stderr)

    def test_best_ranks_both_windows_and_execs_claude_in_place(self):
        self.prepare_accounts((1, 2, 3, 7))
        self.observe(2, 99, 20)
        self.observe(3, 70, 80)
        self.observe(7, 98, 98, reset=int(time.time()) - 1)
        with (self.bin / "claude").open("a") as stub:
            stub.write("print(os.getpid())\nsys.exit(37)\n")
        command = [str(self.bin / "ai-best"), "--", "--resume", "a prompt"]
        with subprocess.Popen(command, env=self.env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) as process:
            output, diagnostics = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 37, diagnostics)
            self.assertEqual(int(output), process.pid)
        self.assertIn("Starting ai3", diagnostics)
        self.assertIn("70%", diagnostics)
        self.assertIn("80%", diagnostics)
        self.assertIn("ai7  5h unknown", diagnostics)
        self.assertNotIn(TOKEN, diagnostics)
        self.assertEqual(self.calls()[0]["token"], f"{TOKEN}-3")
        self.assertEqual(self.calls()[0]["args"][-2:], ["--resume", "a prompt"])

    def test_best_does_not_reuse_observations_after_token_replacement(self):
        self.prepare_accounts((2, 3))
        self.observe(2, 95, 95)
        self.observe(3, 50, 50)
        result = self.account("add", "2", "--paste", stdin="replacement-token\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.account(command="ai-best")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[0]["token"], f"{TOKEN}-3")

    def test_best_uses_legacy_slot_observations_for_ai0_and_login(self):
        self.accounts.mkdir(parents=True)
        (self.accounts / "1.json").write_text(json.dumps({"token": TOKEN}))
        credential = hashlib.sha256(TOKEN.encode()).hexdigest()
        with mock.patch.dict(self.env, {"CLAUDE_ACCOUNT_SLOT": "1", "CLAUDE_ACCOUNT_FINGERPRINT": credential}):
            self.env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
            observed = self.account("observe", stdin=self.usage_input(78, 65))
        self.assertEqual(observed.returncode, 0, observed.stderr)
        result = self.account("status", "0")
        self.assertRegex(result.stdout, r"(?m)^ai0\s+.*78%\s+65%$")

        self.config.mkdir()
        (self.config / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
            "accessToken": TOKEN + "-login", "scopes": ["user:inference"],
        }}))
        (self.config / ".claude.json").write_text(json.dumps({"oauthAccount": {"emailAddress": "same@example.test"}}))
        result = self.account(command="ai-best")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Starting ai0\n", result.stderr)
        self.assertEqual(self.calls()[-1]["token"], TOKEN)

        self.assertEqual(self.account("label", "0", "--username", "same@example.test").returncode, 0)
        result = self.account(command="ai-best")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Starting ai-login\n", result.stderr)
        self.assertIsNone(self.calls()[-1]["token"])

    def test_partial_observation_keeps_the_other_windows_known_limit(self):
        self.prepare_accounts((2,))
        self.observe(2, 90, 9)
        sample = json.loads(self.usage_input(95, 0))
        del sample["rate_limits"]["seven_day"]
        with mock.patch.dict(self.env, {"CLAUDE_CODE_OAUTH_TOKEN": f"{TOKEN}-2"}):
            observed = self.account("observe", stdin=json.dumps(sample))
        self.assertEqual(observed.returncode, 0, observed.stderr)

        result = self.account(command="ai-best")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("7d 9% left · statusline", result.stderr)
        self.assertIn("warning: below 10%", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_best_uses_unknown_account_after_skipping_low_account(self):
        self.prepare_accounts((2, 3))
        self.observe(2, 95, 9)
        result = self.account(command="ai-best")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Starting ai3 with unknown allowance", result.stderr)
        self.assertEqual(self.calls()[0]["token"], f"{TOKEN}-3")

    def test_status_shows_current_cached_usage_and_ignores_an_expired_window(self):
        self.prepare_accounts((2,))
        self.observe(2, 18, 79)
        result = self.account("status", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[1].split()[-2:], ["18%", "79%"])
        self.assertIn("status line", result.stdout)
        self.assertIn("observed", result.stdout)
        self.assertIn("5h reset", result.stdout)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

        sample = json.loads(self.usage_input(18, 0, int(time.time()) - 1))
        del sample["rate_limits"]["seven_day"]
        with mock.patch.dict(self.env, {"CLAUDE_CODE_OAUTH_TOKEN": f"{TOKEN}-2"}):
            self.assertEqual(self.account("observe", stdin=json.dumps(sample)).returncode, 0)
        result = self.account("status", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[1].split()[-2:], ["unavailable", "79%"])
        self.assertEqual(self.calls(), [])

    def test_numbered_session_records_usage_without_exposing_oauth_token_to_observer(self):
        self.prepare_accounts((2,))
        with (self.bin / "claude").open("a") as stub:
            stub.write(f"""
import subprocess
os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN")
if os.environ.get("STUB_REPLACE_TOKEN"):
    subprocess.run(["claude-account", "add", "2", "--paste"],
                   input="replacement-token\\n", text=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=True)
subprocess.run(["claude-account", "observe"], input={self.usage_input(78, 65)!r},
               text=True, check=True)
""")
        launched = self.account(command="ai2")
        self.assertEqual(launched.returncode, 0, launched.stderr)
        status = self.account("status", "2")
        self.assertEqual(status.stdout.splitlines()[1].split()[-2:], ["78%", "65%"])

        self.env["STUB_REPLACE_TOKEN"] = "1"
        launched = self.account(command="ai2")
        self.assertEqual(launched.returncode, 0, launched.stderr)
        status = self.account("status", "2")
        self.assertEqual(status.stdout.splitlines()[1].split()[-2:], ["unavailable", "unavailable"])

    def test_round_rotates_distinct_accounts_and_admits_unknown_windows(self):
        self.prepare_accounts((1, 2, 3, 4, 5, 6, 10))
        self.observe(1, 19, 90)
        self.observe(2, 20, 90)
        sample = json.loads(self.usage_input(90, 19))
        del sample["rate_limits"]["five_hour"]
        with mock.patch.dict(self.env, {"CLAUDE_CODE_OAUTH_TOKEN": f"{TOKEN}-3"}):
            self.assertEqual(self.account("observe", stdin=json.dumps(sample)).returncode, 0)
        self.observe(4, 100, 100, reset=int(time.time()) - 1)
        self.observe(5, 80, 80)
        self.observe(10, 90, 20)
        for slot in (2, 5):
            result = self.account("label", str(slot), "--username", "person@example.test")
            self.assertEqual(result.returncode, 0, result.stderr)
        turns = ((2, ("--resume", "a prompt")), (4, ()), (6, ()), (10, ("--", "--resume")), (2, ()))
        for slot, args in turns:
            result = self.account(*args, command="ai-round")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            note = " with unknown allowance" if slot in (4, 6) else ""
            self.assertEqual(result.stderr, f"Starting ai{slot}{note}\n")
        calls = self.calls()
        self.assertEqual([call["token"] for call in calls], [f"{TOKEN}-{slot}" for slot, _ in turns])
        self.assertEqual(calls[0]["args"][-2:], ["--resume", "a prompt"])
        self.assertEqual(calls[3]["args"][-1], "--resume")

    def test_round_starts_with_no_saved_usage(self):
        self.prepare_accounts((0, 2))
        result = self.account("add", "1", "--paste", stdin=f"{TOKEN}-0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        for slot in (0, 2, 0):
            result = self.account(command="ai-round")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Starting ai{slot} with unknown allowance", result.stderr)
        self.assertEqual([call["token"] for call in self.calls()],
                         [f"{TOKEN}-{slot}" for slot in (0, 2, 0)])

    def test_round_exits_without_launch_when_no_account_qualifies(self):
        self.prepare_accounts((2,))
        self.observe(2, 19, 100)
        result = self.account(command="ai-round")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("20%", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_round_distributes_concurrent_launches_evenly(self):
        slots = (1, 3, 5)
        self.env["CLAUDE_ACCOUNTS_DIR"] = str(self.root / "custom-accounts")
        self.prepare_accounts(slots)
        for slot in slots:
            self.observe(slot, 90, 90)
        with ThreadPoolExecutor(max_workers=12) as workers:
            for result in workers.map(lambda _: self.account(command="ai-round"), range(12)):
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Counter(call["token"] for call in self.calls()),
                         {f"{TOKEN}-{slot}": 4 for slot in slots})

    def test_statusline_warns_when_either_window_is_below_ten_percent(self):
        self.prepare_accounts((2,))
        for five_hour, weekly, warned in ((9.9, 70, True), (70, 9.9, True), (10, 10, False)):
            with self.subTest(five_hour=five_hour, weekly=weekly):
                result = subprocess.run(
                    ["bash", STATUSLINE], cwd=self.root, env=self.env, text=True,
                    input=self.usage_input(five_hour, weekly), capture_output=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual("Low allowance (<10%)" in result.stdout, warned)

    def test_herdr_wrappers_create_layout_and_queue_ai_best_in_returned_pane(self):
        self.env.update(HERDR_ENV="1", HERDR_WORKSPACE_ID="test-workspace")
        herdr = self.bin / "herdr"
        log = self.root / "herdr.jsonl"
        herdr.write_text(f"""#!{sys.executable}
import json, sys
args = sys.argv[1:]
with open({str(log)!r}, "a") as handle:
    handle.write(json.dumps(args) + "\\n")
if args[1] == "create":
    print(json.dumps({{"result": {{"root_pane": {{"pane_id": "returned:p8"}}}}}}))
""")
        herdr.chmod(0o755)
        for kind in ("tab", "workspace"):
            with self.subTest(kind=kind):
                log.write_text("")
                result = self.account(command=f"herdr-new-{kind}-ai-best")
                self.assertEqual(result.returncode, 0, result.stderr)
                create, run = [json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual(create[:4], [kind, "create", "--cwd", os.getcwd()])
                self.assertIn("--no-focus", create)
                self.assertIn(f"CLAUDE_CONFIG_DIR={self.config}", create)
                if kind == "tab":
                    self.assertEqual(create[create.index("--workspace") + 1], "test-workspace")
                else:
                    self.assertNotIn("--workspace", create)
                self.assertEqual(run, ["pane", "run", "returned:p8", "ai-best"])


class UsageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loader = importlib.machinery.SourceFileLoader("claude_account_fixture", str(SCRIPT))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cls.module = importlib.util.module_from_spec(spec)
        loader.exec_module(cls.module)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="claude-report-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / "config"
        self.config.mkdir()
        self.accounts = self.root / "accounts"
        self.accounts.mkdir()
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.root),
                    "CLAUDE_CONFIG_DIR": str(self.config), "CLAUDE_ACCOUNTS_DIR": str(self.accounts)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.creds = self.config / ".credentials.json"
        self.creds.write_text(json.dumps({"claudeAiOauth": {"accessToken": TOKEN, "scopes": ["user:profile"]}}))

    def response(self, payload):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = payload
        return response

    def test_usage_windows_and_fixed_transport(self):
        payload = json.dumps({"five_hour": {"utilization": 0, "resets_at": "2026-11-06T10:00:00Z"},
                              "seven_day": {"utilization": 100, "resets_at": "bad"}, "unknown": TOKEN}).encode()
        opener = mock.Mock()
        opener.open.return_value = self.response(payload)
        with mock.patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            report = self.module.account_report(0)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.anthropic.com/api/oauth/usage")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 5)
        self.assertEqual(request.get_header("Anthropic-beta"), "oauth-2025-04-20")
        output = self.module.render_reports([report])
        self.assertIn("5H LEFT", output)
        self.assertIn("100%", output)
        self.assertIn("0%", output)
        self.assertIn("5h reset 2026-11-06T10:00:00Z", output)
        self.assertIn("week reset unknown", output)
        self.assertIn("usage accepted", output)
        self.assertIn("fetched", output)
        self.assertNotIn(TOKEN, output)
        self.assertNotIn("token", report)

    def test_windows_validate_independently(self):
        for invalid in (None, True, float("nan"), -1, 101, "0", {}, {"utilization": True}, {"utilization": None}):
            value = invalid if not isinstance(invalid, (int, float, str)) else {"utilization": invalid}
            with self.subTest(value=value):
                self.assertIsNone(self.module.window(value))
        self.assertEqual(self.module.window({"utilization": 50, "resets_at": "bad"}),
                         {"remaining": 50, "reset": None})
        payload = json.dumps({"five_hour": {"utilization": 10**400}, "seven_day": {"utilization": 20}}).encode()
        opener = mock.Mock()
        opener.open.return_value = self.response(payload)
        with mock.patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            report = self.module.account_report(0)
        self.assertIsNone(report["usage"]["five_hour"])
        self.assertEqual(report["usage"]["seven_day"]["remaining"], 80)

    def test_transport_failures_are_safe_and_distinct(self):
        for error, reason in [(401, "rejected"), (403, "permission"), (429, "rate limited"), (302, "redirect")]:
            with self.subTest(error=error):
                opener = mock.Mock()
                opener.open.side_effect = urllib.error.HTTPError("https://example.test/" + TOKEN, error, TOKEN, {}, io.BytesIO(TOKEN.encode()))
                with mock.patch.object(self.module.urllib.request, "build_opener", return_value=opener):
                    report = self.module.account_report(0)
                output = self.module.render_reports([report])
                self.assertIn(reason, output)
                self.assertIn("attempted", output)
                self.assertNotIn(TOKEN, output)
                self.assertEqual("rejected by usage endpoint" in output, error == 401)
        opener = mock.Mock()
        opener.open.side_effect = TimeoutError(TOKEN)
        with mock.patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            self.assertNotIn(TOKEN, self.module.render_reports([self.module.account_report(0)]))
        opener.open.side_effect = None
        opener.open.return_value = self.response(b"")
        opener.open.return_value.__enter__.return_value.read.side_effect = http.client.IncompleteRead(b"partial")
        with mock.patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            report = self.module.account_report(0)
        self.assertIn("unavailable", report["usage"]["reason"])
        opener.open.return_value = self.response(b"not json")
        with mock.patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            report = self.module.account_report(0)
        self.assertIn("usage accepted", report["auth"])
        self.assertIsNone(report["usage"]["fetched_at"])
        self.assertIsNone(self.module.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.test"))

    def test_token_missing_and_scopeless_rows_never_contact_network(self):
        (self.accounts / "1.json").write_text(json.dumps({"token": TOKEN, "username": "person@example.test"}))
        self.creds.write_text(json.dumps({"claudeAiOauth": {"accessToken": TOKEN, "scopes": ["user:inference"]}}))
        (self.root / ".claude.json").write_text(json.dumps({"oauthAccount": {"emailAddress": "wrong@example.test"}}))
        with mock.patch.object(self.module.urllib.request, "build_opener", side_effect=AssertionError("network")):
            reports = [self.module.account_report(slot) for slot in (0, 1, 2)]
        self.assertIsNone(reports[0]["username"])
        self.assertEqual(reports[1]["identity_source"], "declared, unverified")
        self.assertIn("profile permission", reports[0]["usage"]["reason"])
        self.assertEqual(reports[2]["auth"], "missing")

    def test_round_does_not_fetch_usage_for_the_stored_login(self):
        (self.accounts / "1.json").write_text(json.dumps({"token": TOKEN + "-1"}))
        with mock.patch.object(self.module, "fetch_usage", side_effect=AssertionError("network")):
            with mock.patch.object(self.module, "run") as launch:
                self.module.run_round([])
        launch.assert_called_once_with(["0"])

    def test_login_identity_follows_native_config_metadata_paths(self):
        default = self.root / ".claude"
        default.mkdir()
        (default / ".credentials.json").write_text(self.creds.read_text())
        for directory, email in ((self.root, "login@example.test"),
                                 (default, "explicit-default@example.test"),
                                 (self.config, "custom@example.test")):
            (directory / ".claude.json").write_text(json.dumps({"oauthAccount": {"emailAddress": email}}))
        for override, email in (("", "login@example.test"),
                                (str(default), "explicit-default@example.test"),
                                (str(self.config), "custom@example.test")):
            with self.subTest(config=override):
                with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": override}):
                    with mock.patch.object(self.module, "fetch_usage", return_value={"accepted": False, "rejected": False}):
                        report = self.module.account_report(0)
                self.assertEqual(report["username"], email)
                self.assertEqual(report["identity_source"], "login cache")


if __name__ == "__main__":
    unittest.main()
