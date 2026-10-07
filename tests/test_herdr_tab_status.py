#!/usr/bin/env python3

import copy
import fcntl
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HELPER = (
    Path(__file__).resolve().parents[1]
    / "private_dot_local/bin/executable_herdr-tab-status"
)


def fixture():
    return {
        "workspaces": [{"workspace_id": "w1", "pane_count": 5}],
        "tabs": [
            {
                "tab_id": "w1:t1",
                "workspace_id": "w1",
                "number": 1,
                "label": "1",
                "agent_status": "working",
            },
            {
                "tab_id": "w1:t2",
                "workspace_id": "w1",
                "number": 2,
                "label": "review",
                "agent_status": "blocked",
            },
            {
                "tab_id": "w1:t3",
                "workspace_id": "w1",
                "number": 3,
                "label": "3",
                "agent_status": "unknown",
            },
            {
                "tab_id": "w1:t4",
                "workspace_id": "w1",
                "number": 4,
                "label": "logs",
                "agent_status": "unknown",
            },
        ],
        "agents": [
            {"tab_id": "w1:t1", "agent": "codex", "agent_status": "working"},
            {"tab_id": "w1:t2", "agent": "claude", "agent_status": "blocked"},
            {"tab_id": "w1:t3", "agent": "codex", "agent_status": "unknown"},
        ],
    }


class HerdrServer:
    """A stateful socket fixture: rename really affects subsequent snapshots."""

    def __init__(self, path):
        self.path = path
        self.snapshot = fixture()
        self.requests = []
        self.metadata = {}
        self.errors = []
        self.drop_next_rename_reply = False
        self.reject_next_rename = False
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(path))
        self.listener.settimeout(0.05)
        self.listener.listen()
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.stop.set()
        self.thread.join(timeout=2)
        self.listener.close()
        if self.errors:
            raise self.errors[0]

    def serve(self):
        while not self.stop.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue
            try:
                with connection, connection.makefile("rwb") as stream:
                    payload = json.loads(stream.readline())
                    with self.lock:
                        self.requests.append(payload)
                        if (
                            payload["method"] == "tab.rename"
                            and self.reject_next_rename
                        ):
                            self.reject_next_rename = False
                            response = {
                                "id": payload["id"],
                                "error": {"message": "rename rejected"},
                            }
                        else:
                            response = {
                                "id": payload["id"],
                                "result": self.handle(
                                    payload["method"], payload["params"]
                                ),
                            }
                            if (
                                payload["method"] == "tab.rename"
                                and self.drop_next_rename_reply
                            ):
                                self.drop_next_rename_reply = False
                                continue
                        stream.write(json.dumps(response).encode() + b"\n")
                        stream.flush()
            except Exception as error:  # noqa: BLE001 - propagate fixture failures to the test thread
                self.errors.append(error)
                return

    def handle(self, method, params):
        if method == "session.snapshot":
            return {
                "type": "session_snapshot",
                "snapshot": copy.deepcopy(self.snapshot),
            }
        if method == "tab.rename":
            self.tab(params["tab_id"])["label"] = params["label"]
            return {
                "type": "tab_info",
                "tab": copy.deepcopy(self.tab(params["tab_id"])),
            }
        if method == "workspace.report_metadata":
            self.assert_metadata_params(params)
            tokens = self.metadata.setdefault(
                (params["workspace_id"], params["source"]), {}
            )
            for key, value in params["tokens"].items():
                if value is None:
                    tokens.pop(key, None)
                else:
                    tokens[key] = value
            return {"type": "workspace_info"}
        raise AssertionError(f"unexpected or focus-changing method: {method}")

    @staticmethod
    def assert_metadata_params(params):
        # The real API clears keys by null values; it has no clear_tokens field.
        assert set(params) <= {"workspace_id", "source", "tokens", "ttl_ms", "seq"}
        assert len(params["tokens"]) <= 16
        assert all(
            value is None or isinstance(value, str)
            for value in params["tokens"].values()
        )

    def tab(self, tab_id):
        return next(tab for tab in self.snapshot["tabs"] if tab["tab_id"] == tab_id)

    def labels(self):
        with self.lock:
            return [tab["label"] for tab in self.snapshot["tabs"]]


class HerdrTabStatusTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="herdr-status-test-")
        self.root = Path(self.temporary.name)
        self.server = HerdrServer(self.root / "herdr.sock")
        self.server.__enter__()
        self.environment = {
            **os.environ,
            "HERDR_ENV": "1",
            "HERDR_SOCKET_PATH": str(self.server.path),
            "XDG_CACHE_HOME": str(self.root / "cache"),
        }
        key = hashlib.sha256(str(self.server.path).encode()).hexdigest()[:20]
        self.directory = self.root / "cache/herdr-tab-status" / key

    def tearDown(self):
        try:
            if self.directory.exists() and not self.lock_available():
                self.command("stop")
                self.wait_for(self.lock_available)
            self.server.__exit__(None, None, None)
        finally:
            self.temporary.cleanup()

    def command(self, name, *args, environment=None):
        return subprocess.run(
            [sys.executable, HELPER, name, *args],
            env=environment or self.environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )

    def success(self, name, *args):
        result = self.command(name, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def tokens(self):
        return self.server.metadata[("w1", "user:tab-status")]

    def lock_available(self):
        path = self.directory / "lock"
        if not path.exists():
            return True
        with path.open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            return True

    def wait_for(self, condition):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.02)
        self.fail("updater did not reach the expected state")

    def test_labels_and_sidebar_distinguish_agents_unknown_and_shell(self):
        self.success("once")
        self.assertEqual(
            self.server.labels(),
            ["1 [▶ Codex]", "review [! Claude]", "3 [? Codex]", "logs [— shell]"],
        )
        self.assertEqual(self.tokens()["tab_inventory"], "4 tabs · 5 panes · 3 agents")
        summary = " ".join(
            value
            for key, value in self.tokens().items()
            if key.startswith("tab_states_")
        )
        for value in ["1 ▶ Codex", "2 ! Claude", "3 ? Codex", "4 — shell"]:
            self.assertIn(value, summary)
        self.assertEqual(self.server.snapshot["tabs"][1]["number"], 2)

    def test_refresh_and_restart_do_not_repeat_suffixes_or_rename_unchanged_tabs(self):
        self.success("once")
        renames = len(
            [
                request
                for request in self.server.requests
                if request["method"] == "tab.rename"
            ]
        )
        self.success("once")
        self.assertEqual(
            len(
                [
                    request
                    for request in self.server.requests
                    if request["method"] == "tab.rename"
                ]
            ),
            renames,
        )
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex]")

    def test_native_done_idle_and_multi_agent_aggregate_states(self):
        self.success("once")
        with self.server.lock:
            self.server.tab("w1:t1")["agent_status"] = "done"
            self.server.tab("w1:t2")["agent_status"] = "idle"
            self.server.snapshot["agents"].append(
                {"tab_id": "w1:t1", "agent": "claude", "agent_status": "done"}
            )
        self.success("once")
        self.assertEqual(self.server.labels()[0], "1 [✓ Claude+Codex ×2]")
        self.assertEqual(self.server.labels()[1], "review [○ Claude]")
        self.assertEqual(self.tokens()["tab_inventory"], "4 tabs · 5 panes · 4 agents")

    def test_agent_exit_replaces_previous_state_with_shell(self):
        self.success("once")
        with self.server.lock:
            self.server.snapshot["agents"] = []
        self.success("once")
        self.assertEqual(self.server.labels()[1], "review [— shell]")
        self.assertEqual(self.tokens()["tab_inventory"], "4 tabs · 5 panes · 0 agents")

    def test_manual_rename_is_preserved_when_refreshing_and_restoring(self):
        self.success("once")
        with self.server.lock:
            self.server.tab("w1:t2")["label"] = "security review"
            self.server.tab("w1:t1")["label"] = "edited [▶ Codex]"
        self.success("once")
        self.assertEqual(self.server.labels()[0], "edited [▶ Codex]")
        self.assertEqual(self.server.labels()[1], "security review [! Claude]")
        self.success("stop")
        self.assertEqual(
            self.server.labels(), ["edited", "security review", "3", "logs"]
        )
        self.assertEqual(self.tokens(), {})

    def test_stop_does_not_overwrite_a_new_unobserved_manual_name(self):
        self.success("once")
        with self.server.lock:
            self.server.tab("w1:t2")["label"] = "new manual name"
        self.success("stop")
        self.assertEqual(self.server.labels(), ["1", "new manual name", "3", "logs"])

    def test_lost_rename_reply_can_recover_original_name(self):
        self.server.drop_next_rename_reply = True
        result = self.command("once")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex]")
        self.success("once")
        self.success("stop")
        self.assertEqual(self.server.labels(), ["1", "review", "3", "logs"])

    def test_rejected_state_change_does_not_lose_previous_decoration(self):
        self.success("once")
        with self.server.lock:
            self.server.tab("w1:t1")["agent_status"] = "idle"
            self.server.reject_next_rename = True
        result = self.command("once")
        self.assertNotEqual(result.returncode, 0)
        self.success("stop")
        self.assertEqual(self.server.labels()[0], "1")

    def test_original_name_that_looks_like_a_marker_survives_a_failed_rename(self):
        with self.server.lock:
            self.server.tab("w1:t1")["label"] = "manual [▶ Codex]"
            self.server.reject_next_rename = True
        self.assertNotEqual(self.command("once").returncode, 0)
        self.success("once")
        self.success("stop")
        self.assertEqual(self.server.labels()[0], "manual [▶ Codex]")

    def test_closed_tabs_prune_the_journal_and_clear_unused_summary_rows(self):
        self.success("once")
        self.assertIn("tab_states_2", self.tokens())
        with self.server.lock:
            self.server.snapshot["tabs"] = self.server.snapshot["tabs"][:1]
            self.server.snapshot["agents"] = self.server.snapshot["agents"][:1]
            self.server.snapshot["workspaces"][0]["pane_count"] = 1
        self.success("once")
        self.assertEqual(self.tokens()["tab_inventory"], "1 tab · 1 pane · 1 agent")
        self.assertNotIn("tab_states_2", self.tokens())
        self.assertEqual(
            list(json.loads((self.directory / "state.json").read_text())["tabs"]),
            ["w1:t1"],
        )

    def test_sidebar_follows_positions_after_tab_reordering(self):
        with self.server.lock:
            self.server.tab("w1:t1")["number"] = 2
            self.server.tab("w1:t2")["number"] = 1
        self.success("once")
        self.assertTrue(
            self.tokens()["tab_states_1"].startswith("1 ! Claude · 2 ▶ Codex")
        )
        self.assertEqual(self.server.labels()[:2], ["1 [▶ Codex]", "review [! Claude]"])

    def test_many_tabs_use_compact_summary_and_keep_each_tab_status(self):
        with self.server.lock:
            self.server.snapshot["tabs"] = [
                {
                    "tab_id": f"w1:t{i}",
                    "workspace_id": "w1",
                    "number": i,
                    "label": str(i),
                    "agent_status": "working",
                }
                for i in range(1, 61)
            ]
            self.server.snapshot["agents"] = [
                {"tab_id": f"w1:t{i}", "agent": "codex"} for i in range(1, 61)
            ]
            self.server.snapshot["workspaces"][0]["pane_count"] = 60
        self.success("once")
        rows = [
            value
            for key, value in self.tokens().items()
            if key.startswith("tab_states_")
        ]
        markers = " ".join(rows).split()
        self.assertEqual(markers, [f"{i}▶" for i in range(1, 61)])
        self.assertLessEqual(len(rows), 13)

    def test_metadata_from_other_reporters_survives_stop(self):
        self.server.metadata[("w1", "user:git-dirty")] = {"git_dirty": "*"}
        self.success("once")
        self.success("stop")
        self.assertEqual(
            self.server.metadata[("w1", "user:git-dirty")], {"git_dirty": "*"}
        )

    def test_original_names_and_cleanup_are_scoped_to_the_session_socket(self):
        self.success("once")
        with HerdrServer(self.root / "other.sock") as other:
            other.tab("w1:t1")["label"] = "another session"
            environment = {**self.environment, "HERDR_SOCKET_PATH": str(other.path)}
            result = self.command("once", environment=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(other.labels()[0], "another session [▶ Codex]")
            self.success("stop")
            self.assertEqual(other.labels()[0], "another session [▶ Codex]")
            result = self.command("stop", environment=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(other.labels()[0], "another session")

    def test_preview_is_read_only_and_creates_no_journal(self):
        result = self.success("preview")
        plan = json.loads(result.stdout)
        self.assertEqual(plan["tabs"][1]["label"], "review [! Claude]")
        self.assertEqual(self.server.labels(), ["1", "review", "3", "logs"])
        self.assertEqual(
            [request["method"] for request in self.server.requests],
            ["session.snapshot"],
        )
        self.assertFalse(self.directory.exists())

    def test_incomplete_snapshot_does_not_rename_or_publish_false_shell_states(self):
        del self.server.snapshot["agents"]
        result = self.command("once")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing workspace, tab, or agent lists", result.stderr)
        self.assertEqual(
            [request["method"] for request in self.server.requests],
            ["session.snapshot"],
        )
        self.assertEqual(self.server.labels(), ["1", "review", "3", "logs"])

    def test_invalid_journal_fails_without_mutations(self):
        self.directory.mkdir(parents=True)
        (self.directory / "state.json").write_text('{"version":2,"tabs":{}}')
        result = self.command("once")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid label journal", result.stderr)
        self.assertEqual(self.server.requests, [])

    def test_refuses_to_control_a_session_from_outside_herdr(self):
        environment = {**self.environment, "HERDR_ENV": "0"}
        result = self.command("once", environment=environment)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.server.requests, [])

    def test_start_is_singleton_and_stop_restores_names_without_blocking_shell(self):
        started = time.monotonic()
        self.success("start", "--interval", "0.05")
        self.assertLess(time.monotonic() - started, 2)
        self.wait_for(lambda: self.server.labels()[3] == "logs [— shell]")
        self.success("start", "--interval", "0.05")
        result = self.command("once")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already running", result.stderr)
        self.success("stop")
        self.wait_for(self.lock_available)
        self.assertEqual(self.server.labels(), ["1", "review", "3", "logs"])
        self.assertEqual(self.tokens(), {})


if __name__ == "__main__":
    unittest.main()
