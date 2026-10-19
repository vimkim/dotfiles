#!/usr/bin/env python3

import copy
import fcntl
import hashlib
import json
import os
import queue
import runpy
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

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
        self.subscribers = {}
        self.handlers = []
        self.before_snapshot_reply = None
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
        for handler in self.handlers:
            handler.join(timeout=2)
        if self.errors:
            raise self.errors[0]

    def serve(self):
        while not self.stop.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue
            handler = threading.Thread(
                target=self.serve_request, args=(connection,), daemon=True
            )
            self.handlers.append(handler)
            handler.start()

    def serve_request(self, connection):
        try:
            with connection, connection.makefile("rwb") as stream:
                payload = json.loads(stream.readline())
                if payload["method"] == "events.subscribe":
                    self.serve_subscription(connection, stream, payload)
                    return
                with self.lock:
                    self.requests.append(payload)
                    if payload["method"] == "tab.rename" and self.reject_next_rename:
                        self.reject_next_rename = False
                        response = {
                            "id": payload["id"],
                            "error": {"message": "rename rejected"},
                        }
                    else:
                        response = {
                            "id": payload["id"],
                            "result": self.handle(payload["method"], payload["params"]),
                        }
                        if (
                            payload["method"] == "tab.rename"
                            and self.drop_next_rename_reply
                        ):
                            self.drop_next_rename_reply = False
                            return
                    callback = self.before_snapshot_reply
                    if payload["method"] == "session.snapshot":
                        self.before_snapshot_reply = None
                    else:
                        callback = None
                if callback:
                    callback()
                stream.write(json.dumps(response).encode() + b"\n")
                stream.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            self.errors.append(error)

    def serve_subscription(self, connection, stream, payload):
        events = queue.Queue()
        with self.lock:
            self.requests.append(payload)
            self.subscribers[connection] = (
                {entry["type"] for entry in payload["params"]["subscriptions"]},
                events,
            )
        try:
            stream.write(json.dumps({
                "id": payload["id"], "result": {"type": "subscription_started"}
            }).encode() + b"\n")
            stream.flush()
            while not self.stop.is_set():
                try:
                    event = events.get(timeout=0.05)
                except queue.Empty:
                    continue
                if event is None:
                    return
                stream.write(json.dumps(event).encode() + b"\n")
                stream.flush()
                if "error" in event:
                    return
        finally:
            with self.lock:
                self.subscribers.pop(connection, None)

    def emit(self, kind, data):
        with self.lock:
            for subscriptions, events in self.subscribers.values():
                if kind.replace("_", ".", 1) in subscriptions:
                    events.put({"event": kind, "data": {"type": kind, **data}})

    def disconnect_subscribers(self, error=None):
        with self.lock:
            for _subscriptions, events in self.subscribers.values():
                events.put(
                    {"id": "tab-status-events", "error": error} if error else None
                )

    def handle(self, method, params):
        if method == "session.snapshot":
            return {
                "type": "session_snapshot",
                "snapshot": copy.deepcopy(self.snapshot),
            }
        if method == "tab.rename":
            self.tab(params["tab_id"])["label"] = params["label"]
            self.emit("tab_renamed", {
                "tab_id": params["tab_id"],
                "workspace_id": "w1",
                "label": params["label"],
            })
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

    def update_at(self, timestamp):
        self.directory.mkdir(parents=True, exist_ok=True)
        module = runpy.run_path(str(HELPER))
        with mock.patch("time.time", return_value=timestamp):
            return module["Updater"](str(self.server.path), self.directory).update()

    def test_elapsed_time_advances_in_labels_and_sidebar_across_restarts(self):
        self.update_at(1000)
        renames = sum(
            request["method"] == "tab.rename" for request in self.server.requests
        )
        self.update_at(1059)
        self.assertEqual(
            sum(request["method"] == "tab.rename" for request in self.server.requests),
            renames,
        )
        for elapsed, duration in (
            (60, "1m"),
            (480, "8m"),
            (3540, "59m"),
            (3600, "1h00m"),
            (3720, "1h02m"),
            (86400, "1d00h"),
            (97200, "1d03h"),
        ):
            with self.subTest(elapsed=elapsed):
                self.update_at(1000 + elapsed)
                self.assertEqual(self.server.labels()[0], f"1 [▶ Codex {duration}]")
                self.assertEqual(
                    self.server.labels()[1], f"2 review [! Claude {duration}]"
                )
                self.assertIn(f"1 ▶ Codex {duration}", self.tokens()["tab_states_1"])
                self.assertEqual(self.server.labels()[3], "4 logs [— shell]")
        self.success("stop")
        self.assertEqual(self.server.labels(), ["1", "review", "3", "logs"])

    def test_state_transitions_reset_only_the_changed_tab_timer(self):
        self.update_at(1000)
        with self.server.lock:
            self.server.tab("w1:t1")["agent_status"] = "blocked"
        self.update_at(1480)
        self.assertEqual(self.server.labels()[0], "1 [! Codex <1m]")
        self.assertEqual(self.server.labels()[1], "2 review [! Claude 8m]")
        for index, state in enumerate(("done", "idle", "unknown", "working"), 1):
            with self.subTest(state=state):
                with self.server.lock:
                    self.server.tab("w1:t1")["agent_status"] = state
                plan = self.update_at(1480 + index * 120)
                self.assertEqual(plan["tabs"][0]["duration"], "<1m")
                self.assertEqual(plan["tabs"][0]["state_since"], 1480 + index * 120)

    def test_agent_exit_and_return_start_a_new_timer(self):
        self.update_at(1000)
        with self.server.lock:
            agent = self.server.snapshot["agents"].pop(0)
        self.update_at(1480)
        self.assertEqual(self.server.labels()[0], "1 [— shell]")
        with self.server.lock:
            self.server.snapshot["agents"].append(agent)
        self.update_at(1600)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex <1m]")

    def test_timer_tracks_aggregate_state_when_agent_membership_changes(self):
        self.update_at(1000)
        with self.server.lock:
            self.server.snapshot["agents"].append(
                {"tab_id": "w1:t1", "agent": "claude", "agent_status": "working"}
            )
        self.update_at(1480)
        self.assertEqual(self.server.labels()[0], "1 [▶ Claude+Codex ×2 8m]")
        with self.server.lock:
            self.server.tab("w1:t1")["agent_status"] = "blocked"
            self.server.snapshot["agents"][-1]["agent_status"] = "blocked"
        self.update_at(1540)
        self.assertEqual(self.server.labels()[0], "1 [! Claude+Codex ×2 <1m]")

    def test_manual_names_and_tab_order_changes_do_not_reset_timers(self):
        self.update_at(1000)
        self.update_at(1480)
        with self.server.lock:
            self.server.tab("w1:t1")["label"] = "renamed [▶ Codex 8m]"
            self.server.snapshot["tabs"][:2] = self.server.snapshot["tabs"][:2][::-1]
        self.update_at(1540)
        self.assertEqual(self.server.tab("w1:t1")["label"], "2 renamed [▶ Codex 9m]")
        self.assertTrue(self.tokens()["tab_states_1"].startswith("1 ! Claude 9m"))
        self.success("stop")
        self.assertEqual(self.server.tab("w1:t1")["label"], "renamed")

    def test_lost_age_rename_reply_preserves_original_name_and_timer(self):
        self.update_at(1000)
        self.server.drop_next_rename_reply = True
        with self.assertRaisesRegex(RuntimeError, "incomplete response"):
            self.update_at(1480)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex 8m]")
        self.update_at(1540)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex 9m]")
        self.success("stop")
        self.assertEqual(self.server.labels(), ["1", "review", "3", "logs"])

    def test_legacy_journal_migrates_without_repeating_status_suffixes(self):
        self.directory.mkdir(parents=True)
        with self.server.lock:
            self.server.tab("w1:t1")["label"] = "1 [▶ Codex]"
        legacy = {
            "version": 1,
            "tabs": {
                "w1:t1": {
                    "base": "1",
                    "labels": ["1 [▶ Codex]"],
                    "suffixes": [" [▶ Codex]"],
                }
            },
        }
        (self.directory / "state.json").write_text(json.dumps(legacy))
        self.update_at(1000)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex <1m]")
        self.update_at(1480)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex 8m]")
        self.success("stop")
        self.assertEqual(self.server.labels()[0], "1")

    def test_clock_moving_backwards_rebases_the_timer_without_negative_age(self):
        self.update_at(1000)
        self.update_at(900)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex <1m]")
        self.update_at(1020)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex 2m]")

    def test_preview_uses_persisted_age_without_saving_new_observations(self):
        self.update_at(1000)
        previous_journal = (self.directory / "state.json").read_text()
        previous_requests = len(self.server.requests)
        module = runpy.run_path(str(HELPER))
        with self.server.lock:
            self.server.tab("w1:t2")["agent_status"] = "idle"
        with mock.patch("time.time", return_value=1480):
            plan = module["Updater"](str(self.server.path), self.directory).preview()
        self.assertEqual(plan["tabs"][0]["duration"], "8m")
        self.assertEqual(plan["tabs"][1]["duration"], "<1m")
        self.assertEqual((self.directory / "state.json").read_text(), previous_journal)
        self.assertEqual(
            [request["method"] for request in self.server.requests[previous_requests:]],
            ["session.snapshot"],
        )

    def test_invalid_timing_in_journal_fails_without_runtime_mutations(self):
        self.update_at(1000)
        valid = json.loads((self.directory / "state.json").read_text())
        for timing in (
            {"state": "invalid", "state_since": 1000},
            {"state": "working", "state_since": "1000"},
            {"state": "working", "state_since": True},
            {"state": "working", "state_since": float("inf")},
            {"state": "working", "state_since": -1},
            {"state": "working"},
            {"state_since": 1000},
        ):
            with self.subTest(timing=timing):
                invalid = copy.deepcopy(valid)
                record = invalid["tabs"]["w1:t1"]
                del record["state"]
                del record["state_since"]
                record.update(timing)
                (self.directory / "state.json").write_text(json.dumps(invalid))
                previous_requests = len(self.server.requests)
                result = self.command("once")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid label journal", result.stderr)
                self.assertEqual(len(self.server.requests), previous_requests)
        (self.directory / "state.json").write_text(json.dumps(valid))

    def test_labels_and_sidebar_distinguish_agents_unknown_and_shell(self):
        self.success("once")
        self.assertEqual(
            self.server.labels(),
            [
                "1 [▶ Codex <1m]",
                "2 review [! Claude <1m]",
                "3 [? Codex <1m]",
                "4 logs [— shell]",
            ],
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
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex <1m]")

    def test_native_done_idle_and_multi_agent_aggregate_states(self):
        self.success("once")
        with self.server.lock:
            self.server.tab("w1:t1")["agent_status"] = "done"
            self.server.tab("w1:t2")["agent_status"] = "idle"
            self.server.snapshot["agents"].append(
                {"tab_id": "w1:t1", "agent": "claude", "agent_status": "done"}
            )
        self.success("once")
        self.assertEqual(self.server.labels()[0], "1 [✓ Claude+Codex ×2 <1m]")
        self.assertEqual(self.server.labels()[1], "2 review [○ Claude <1m]")
        self.assertEqual(self.tokens()["tab_inventory"], "4 tabs · 5 panes · 4 agents")

    def test_agent_exit_replaces_previous_state_with_shell(self):
        self.success("once")
        with self.server.lock:
            self.server.snapshot["agents"] = []
        self.success("once")
        self.assertEqual(self.server.labels()[1], "2 review [— shell]")
        self.assertEqual(self.tokens()["tab_inventory"], "4 tabs · 5 panes · 0 agents")

    def test_manual_rename_is_preserved_when_refreshing_and_restoring(self):
        self.success("once")
        with self.server.lock:
            self.server.tab("w1:t2")["label"] = "security review"
            self.server.tab("w1:t1")["label"] = "edited [▶ Codex <1m]"
        self.success("once")
        self.assertEqual(self.server.labels()[0], "1 edited [▶ Codex <1m]")
        self.assertEqual(self.server.labels()[1], "2 security review [! Claude <1m]")
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

    def test_manual_rename_with_managed_number_and_suffix_restores_only_the_name(self):
        self.update_at(1000)
        with self.server.lock:
            self.server.tab("w1:t2")["label"] = "2 security review [! Claude <1m]"
        self.update_at(1480)
        self.assertEqual(self.server.labels()[1], "2 security review [! Claude 8m]")
        self.success("stop")
        self.assertEqual(self.server.labels()[1], "security review")

    def test_stop_recognizes_manual_edit_with_old_prefix_after_rejected_reorder(self):
        self.update_at(1000)
        with self.server.lock:
            self.server.snapshot["tabs"][:2] = self.server.snapshot["tabs"][:2][::-1]
            self.server.reject_next_rename = True
        with self.assertRaisesRegex(RuntimeError, "rename rejected"):
            self.update_at(1480)
        with self.server.lock:
            self.server.tab("w1:t2")["label"] = "2 renamed [! Claude <1m]"
        self.success("stop")
        self.assertEqual(self.server.labels(), ["renamed", "1", "3", "logs"])

    def test_lost_reorder_reply_recovers_without_duplicating_numbers(self):
        self.update_at(1000)
        with self.server.lock:
            self.server.snapshot["tabs"][:2] = self.server.snapshot["tabs"][:2][::-1]
            self.server.drop_next_rename_reply = True
        with self.assertRaisesRegex(RuntimeError, "incomplete response"):
            self.update_at(1480)
        self.update_at(1540)
        self.assertEqual(
            self.server.labels()[:2], ["1 review [! Claude 9m]", "2 [▶ Codex 9m]"]
        )
        self.success("stop")
        self.assertEqual(self.server.labels(), ["review", "1", "3", "logs"])

    def test_lost_rename_reply_can_recover_original_name(self):
        self.server.drop_next_rename_reply = True
        result = self.command("once")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex <1m]")
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
            self.server.tab("w1:t1")["label"] = "manual [▶ Codex <1m]"
            self.server.reject_next_rename = True
        self.assertNotEqual(self.command("once").returncode, 0)
        self.success("once")
        self.success("stop")
        self.assertEqual(self.server.labels()[0], "manual [▶ Codex <1m]")

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

    def test_labels_and_sidebar_follow_positions_after_tab_reordering(self):
        self.update_at(1000)
        with self.server.lock:
            # Native tab.move changes array order, never a tab's creation number.
            self.server.snapshot["tabs"][:2] = self.server.snapshot["tabs"][:2][::-1]
        self.update_at(1480)
        self.assertTrue(
            self.tokens()["tab_states_1"].startswith("1 ! Claude 8m · 2 ▶ Codex 8m")
        )
        self.assertEqual(
            self.server.labels()[:2], ["1 review [! Claude 8m]", "2 [▶ Codex 8m]"]
        )
        self.update_at(1540)
        self.assertEqual(
            self.server.labels()[:2], ["1 review [! Claude 9m]", "2 [▶ Codex 9m]"]
        )
        self.assertEqual(
            [tab["number"] for tab in self.server.snapshot["tabs"]], [2, 1, 3, 4]
        )
        self.success("stop")
        self.assertEqual(self.server.labels(), ["review", "1", "3", "logs"])

    def test_positions_reset_per_workspace_despite_gaps_in_creation_numbers(self):
        with self.server.lock:
            self.server.snapshot["workspaces"].append(
                {"workspace_id": "w2", "pane_count": 1}
            )
            self.server.snapshot["tabs"] = [
                {**self.server.tab("w1:t1"), "number": 12, "label": "12"},
                {
                    "tab_id": "w2:t9",
                    "workspace_id": "w2",
                    "number": 9,
                    "label": "9",
                    "agent_status": "unknown",
                },
            ]
            self.server.snapshot["agents"] = self.server.snapshot["agents"][:1]
        self.update_at(1000)
        self.assertEqual(self.server.labels(), ["1 [▶ Codex <1m]", "1 [— shell]"])
        self.assertEqual(self.tokens()["tab_states_1"], "1 ▶ Codex <1m")
        self.assertEqual(
            self.server.metadata[("w2", "user:tab-status")]["tab_states_1"], "1 — shell"
        )
        self.success("stop")
        self.assertEqual(self.server.labels(), ["12", "9"])

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
        self.assertEqual(markers, [f"{i}▶<1m" for i in range(1, 61)])
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
            self.assertEqual(other.labels()[0], "1 another session [▶ Codex <1m]")
            self.success("stop")
            self.assertEqual(other.labels()[0], "1 another session [▶ Codex <1m]")
            result = self.command("stop", environment=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(other.labels()[0], "another session")

    def test_preview_is_read_only_and_creates_no_journal(self):
        result = self.success("preview")
        plan = json.loads(result.stdout)
        self.assertEqual(plan["tabs"][1]["label"], "2 review [! Claude <1m]")
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

    def request_count(self, method):
        with self.server.lock:
            return sum(request["method"] == method for request in self.server.requests)

    def start_worker(self):
        self.success("start", "--retry-delay", "0.05")
        self.wait_for(lambda: self.server.labels()[3] == "4 logs [— shell]")

    def test_idle_worker_and_own_renames_do_not_poll_snapshots(self):
        self.start_worker()
        time.sleep(0.3)
        self.assertEqual(self.request_count("session.snapshot"), 1)
        self.assertEqual(self.request_count("events.subscribe"), 1)
        with self.server.lock:
            self.server.snapshot["tabs"][:2] = self.server.snapshot["tabs"][:2][::-1]
            self.server.emit("tab_moved", {"tab_id": "w1:t2", "workspace_id": "w1"})
        self.wait_for(lambda: self.server.tab("w1:t2")["label"].startswith("1 review "))
        time.sleep(0.3)
        self.assertEqual(self.request_count("session.snapshot"), 2)

    def test_tab_add_and_close_events_renumber_and_refresh_inventory(self):
        self.start_worker()
        added = {
            "tab_id": "w1:t12", "workspace_id": "w1", "number": 12,
            "label": "12", "agent_status": "unknown",
        }
        with self.server.lock:
            self.server.snapshot["tabs"].insert(0, added)
            self.server.emit("tab_created", {"tab": copy.deepcopy(added)})
        self.wait_for(lambda: self.server.tab("w1:t1")["label"].startswith("2 "))
        self.wait_for(lambda: self.tokens()["tab_inventory"].startswith("5 tabs"))
        with self.server.lock:
            self.server.snapshot["tabs"].remove(added)
            self.server.emit("tab_closed", {"tab_id": "w1:t12", "workspace_id": "w1"})
        self.wait_for(lambda: self.server.tab("w1:t1")["label"].startswith("1 "))
        self.wait_for(lambda: self.tokens()["tab_inventory"].startswith("4 tabs"))

    def test_pane_events_ignore_title_only_changes_and_refresh_agent_state(self):
        pane = {
            "pane_id": "w1:p1", "workspace_id": "w1", "tab_id": "w1:t1",
            "agent": "codex", "agent_status": "working",
        }
        self.server.snapshot["panes"] = [pane]
        self.start_worker()
        baseline = self.request_count("session.snapshot")
        self.server.emit("pane_updated", {"pane": {**pane, "terminal_title": "updated"}})
        time.sleep(0.3)
        self.assertEqual(self.request_count("session.snapshot"), baseline)
        with self.server.lock:
            pane["agent_status"] = "blocked"
            self.server.tab("w1:t1")["agent_status"] = "blocked"
            self.server.emit("pane_updated", {"pane": copy.deepcopy(pane)})
        self.wait_for(lambda: self.server.labels()[0] == "1 [! Codex <1m]")
        self.assertGreater(self.request_count("events.subscribe"), 1)

    def test_events_arriving_during_snapshot_cause_a_followup_read(self):
        def reorder_during_read():
            with self.server.lock:
                self.server.snapshot["tabs"][:2] = self.server.snapshot["tabs"][:2][::-1]
                self.server.emit("tab_moved", {"tab_id": "w1:t2", "workspace_id": "w1"})

        self.server.before_snapshot_reply = reorder_during_read
        self.start_worker()
        self.wait_for(lambda: self.request_count("session.snapshot") >= 2)
        self.wait_for(lambda: self.server.labels()[:2] == [
            "1 review [! Claude <1m]", "2 [▶ Codex <1m]"
        ])

    def test_lost_event_history_and_disconnect_resubscribe_and_reconcile(self):
        self.start_worker()
        for error in ({"code": "events_lost", "message": "history overrun"}, None):
            with self.subTest(error=error):
                subscriptions = self.request_count("events.subscribe")
                with self.server.lock:
                    self.server.snapshot["tabs"][:2] = (
                        self.server.snapshot["tabs"][:2][::-1]
                    )
                    self.server.disconnect_subscribers(error)
                self.wait_for(
                    lambda: self.request_count("events.subscribe") > subscriptions
                )
                self.wait_for(lambda: self.server.labels()[0].startswith("1 "))

    def test_cached_timer_updates_renew_metadata_without_snapshot_reads(self):
        self.directory.mkdir(parents=True)
        module = runpy.run_path(str(HELPER))
        updater = module["Updater"](str(self.server.path), self.directory)
        snapshot = updater.snapshot()
        with (
            mock.patch("time.time", return_value=1000),
            mock.patch("time.monotonic", return_value=100),
        ):
            plan = updater.update(snapshot)
            self.assertEqual(module["timer_delay"](updater, plan), 20)
        with (
            mock.patch("time.time", return_value=1060),
            mock.patch("time.monotonic", return_value=160),
        ):
            updater.update(snapshot)
        self.assertEqual(self.server.labels()[0], "1 [▶ Codex 1m]")
        self.assertEqual(self.request_count("session.snapshot"), 1)
        self.assertEqual(self.request_count("workspace.report_metadata"), 2)

    def test_start_is_singleton_and_stop_restores_names_without_blocking_shell(self):
        started = time.monotonic()
        self.success("start", "--interval", "0.05")
        self.assertLess(time.monotonic() - started, 2)
        self.wait_for(lambda: self.server.labels()[3] == "4 logs [— shell]")
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
