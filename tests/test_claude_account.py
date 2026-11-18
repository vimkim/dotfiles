"""Exercise claude-account slots and the ai/aiN shortcuts without a real Claude login."""

import json
import hashlib
import http.client
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock
import urllib.error


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "private_dot_config/my-scripts/bin/executable_claude-account"
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
        shutil.copyfile(SCRIPT, self.bin / "claude-account")
        (self.bin / "claude-account").chmod(0o755)
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

    def test_slot_zero_uses_stored_login_and_drops_inherited_credentials(self):
        self.env["CLAUDE_CODE_OAUTH_TOKEN"] = "inherited-from-ai2"
        self.env["ANTHROPIC_API_KEY"] = "inherited-api"
        self.env["ANTHROPIC_AUTH_TOKEN"] = "inherited-auth"
        self.accounts.mkdir(parents=True)
        (self.accounts / "0.json").write_text(json.dumps({"token": TOKEN}))
        result = self.account("run", "0", "-c", "two words")
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = str(self.config / "local-settings.json")
        self.assertEqual(self.calls(), [{"name": "claude", "token": None, "api": None, "auth": None, "args": [
            "--settings", settings, "--dangerously-skip-permissions", "-c", "two words"]}])

    def test_settings_fall_back_to_home_claude_when_config_dir_is_empty(self):
        self.env["CLAUDE_CONFIG_DIR"] = ""
        self.env["HOME"] = str(self.root / "home")
        with (self.bin / "claude").open("a") as stub:
            stub.write('assert "CLAUDE_CONFIG_DIR" not in os.environ\n')
        self.assertEqual(self.account("run", "0").returncode, 0)
        self.assertEqual(self.calls()[0]["args"][1],
                         str(self.root / "home/.claude/local-settings.json"))

    def test_added_slot_passes_its_token_and_stays_private(self):
        self.add_slot(2, "--label", "personal")
        stored = self.accounts / "2.json"
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
        for args in (("add", "0", "--paste"), ("remove", "0"), ("add", "x", "--paste"), ("add", "2", "--bogus")):
            with self.subTest(args=args):
                self.assertEqual(self.account(*args).returncode, 2)
        self.assertEqual(self.account("add", "2", "--paste", stdin="two words\n").returncode, 1)
        self.assertFalse((self.accounts / "2.json").exists())

    def test_list_shows_slots_without_tokens_and_remove_deletes(self):
        self.add_slot(2, "--label", "personal")
        listing = self.account("list")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn("ai/ai0  /login", listing.stdout)
        self.assertIn("ai1  not configured", listing.stdout)
        self.assertIn("ai2  token", listing.stdout)
        self.assertIn("personal", listing.stdout)
        self.assertNotIn(TOKEN, listing.stdout)
        self.assertEqual(self.account("remove", "2").returncode, 0)
        self.assertEqual(self.account("run", "2").returncode, 1)

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
        (self.accounts / "4.json").write_text(json.dumps({"token": TOKEN, "added": "bad"}))
        paths = list(self.accounts.iterdir())
        before = {p: hashlib.sha256(p.read_bytes()).digest() for p in paths}
        result = self.account("status", "--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        for value in ("ai/ai0", "ai1", "ai2", "ai4", "unreadable or invalid", "team\\u000aname"):
            self.assertIn(value, result.stdout)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).digest() for p in paths})
        self.assertIn("renewal estimate unavailable", self.account("list").stdout)
        self.assertEqual(self.calls(), [])

    def test_label_preserves_existing_data_and_private_mode(self):
        self.add_slot(2, "--label", "team")
        path = self.accounts / "2.json"
        existing = json.loads(path.read_text())
        existing["extra"] = {"keep": True}
        path.write_text(json.dumps(existing))
        result = self.account("label", "2", "--username", "team@example.test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.read_text()), {**existing, "username": "team@example.test"})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.account("label", "0", "--label", "x").returncode, 2)
        self.assertEqual(self.account("status", "2", "--all").returncode, 2)
        self.assertEqual(self.account("list", "extra").returncode, 2)

    def test_missing_and_malformed_slot_one_never_launch(self):
        self.assertEqual(self.account("run", "1").returncode, 1)
        self.accounts.mkdir(parents=True)
        (self.accounts / "1.json").write_text("not json")
        self.assertEqual(self.account("run", "1").returncode, 1)
        (self.accounts / "1.json").write_text(json.dumps({"token": "bad\x00token"}))
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
        for slot in range(1, 10):
            (self.accounts / f"{slot}.json").write_text(json.dumps({"token": f"{TOKEN}-{slot}"}))
        settings = ["--settings", str(self.config / "local-settings.json"), "--dangerously-skip-permissions"]
        args = ["123", "two words", "", "--resume"]
        for name, slot in [("ai", 0), *((f"ai{slot}", slot) for slot in range(10))]:
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

    def prepare_best(self, slots):
        self.env.update(HOME=str(self.root), HERDR_ENV="1", HERDR_WORKSPACE_ID="test-workspace")
        self.herdr_log = self.root / "herdr.jsonl"
        self.env["HERDR_LOG"] = str(self.herdr_log)
        herdr = self.bin / "herdr"
        herdr.write_text(f"""#!{sys.executable}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["HERDR_LOG"], "a") as handle:
    handle.write(json.dumps(args) + "\\n")
if args[:2] == ["tab", "create"]:
    print(json.dumps({{"result": {{"tab": {{"tab_id": "test:t1"}},
                                  "root_pane": {{"pane_id": "test:p1"}}}}}}))
""")
        herdr.chmod(0o755)
        for slot in slots:
            result = self.account("add", str(slot), "--paste", stdin=f"{TOKEN}-{slot}\n")
            self.assertEqual(result.returncode, 0, result.stderr)

    def tab_calls(self):
        return [json.loads(line) for line in self.herdr_log.read_text().splitlines()]

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

    def test_best_ranks_both_windows_and_keeps_unknown_accounts_as_backups(self):
        self.prepare_best((1, 2, 3, 7))
        self.observe(2, 99, 20)
        self.observe(3, 70, 80)
        self.observe(7, 98, 98, reset=int(time.time()) - 1)
        result = self.account(command="ai-best")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ai3", result.stdout)
        self.assertIn("70%", result.stdout)
        self.assertIn("80%", result.stdout)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        create, launch = self.tab_calls()
        self.assertEqual(create[:4], ["tab", "create", "--workspace", "test-workspace"])
        self.assertIn("--no-focus", create)
        self.assertEqual(launch[:3], ["pane", "run", "test:p1"])
        command = shlex.split(launch[-1])
        self.assertRegex(command[1], r"^CLAUDE_ACCOUNT_RETRY=[0-9a-f]{32}$")
        self.assertEqual(command[2:], ["claude-account", "run", "3"])

    def test_best_does_not_reuse_observations_after_token_replacement(self):
        self.prepare_best((2, 3))
        self.observe(2, 95, 95)
        self.observe(3, 50, 50)
        result = self.account("add", "2", "--paste", stdin="replacement-token\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.account(command="ai-best")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.tab_calls()[-1][-1].endswith("claude-account run 3"))

    def test_partial_observation_keeps_the_other_windows_known_limit(self):
        self.prepare_best((2,))
        self.observe(2, 90, 9)
        sample = json.loads(self.usage_input(95, 0))
        del sample["rate_limits"]["seven_day"]
        with mock.patch.dict(self.env, {"CLAUDE_CODE_OAUTH_TOKEN": f"{TOKEN}-2"}):
            observed = self.account("observe", stdin=json.dumps(sample))
        self.assertEqual(observed.returncode, 0, observed.stderr)

        result = self.account(command="ai-best")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("7d 9%", result.stdout)
        self.assertFalse(self.herdr_log.exists())

    def test_low_observation_opens_one_alternative_under_concurrent_status_updates(self):
        self.prepare_best((2, 3, 4))
        for slot in (2, 4):
            labeled = self.account("label", str(slot), "--username", "same@example.test")
            self.assertEqual(labeled.returncode, 0, labeled.stderr)
        self.observe(2, 90, 90)
        self.observe(3, 80, 80)
        self.observe(4, 85, 85)
        result = self.account(command="ai-best")
        self.assertEqual(result.returncode, 0, result.stderr)
        create, launch = self.tab_calls()
        command = shlex.split(launch[-1])
        self.assertEqual(command[2:], ["claude-account", "run", "2"])

        with (self.bin / "claude").open("a") as stub:
            fixture = self.usage_input(90, 9)
            stub.write(f"""
import subprocess
subprocess.run(["claude-account", "observe"], input={fixture!r}, text=True, check=True)
""")
        tab_env = {key: value for key, value in
                   (create[index + 1].split("=", 1)
                    for index, arg in enumerate(create) if arg == "--env")}
        self.assertNotIn("CLAUDE_ACCOUNT_RETRY", tab_env)
        env = {**self.env, **tab_env, "HERDR_PANE_ID": "test:p1"}
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(
                lambda _: subprocess.run(command, env=env, input="", capture_output=True, text=True, timeout=10),
                range(4)))
        for outcome in results:
            self.assertEqual(outcome.returncode, 0, outcome.stderr)
        deadline = time.monotonic() + 5
        while len(self.tab_calls()) < 5 and time.monotonic() < deadline:
            time.sleep(0.025)
        first_tab, first_launch, fallback_tab, fallback_launch = [
            args for args in self.tab_calls() if args[0] in ("tab", "pane")
        ]
        self.assertEqual((first_tab, first_launch), (create, launch))
        self.assertIn("--no-focus", fallback_tab)
        self.assertEqual(fallback_launch, [
            "pane", "run", "test:p1", "env CLAUDE_ACCOUNT_RETRY= claude-account run 3"
        ])


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
