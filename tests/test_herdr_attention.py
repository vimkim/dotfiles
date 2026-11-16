import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_herdr_tab_status import HerdrServer

HELPER = Path(__file__).resolve().parents[1] / "private_dot_local/bin/executable_herdr-attention"
RULE = "─" * 30


def screen(footer="⏵⏵ bypass permissions on", history="", above=""):
    return f"{history}\n{above}\n{RULE}\n❯\n{RULE}\n{footer}\n"


class Server(HerdrServer):
    def __init__(self, path):
        super().__init__(path)
        self.texts = {}
        self.refreshed_states = {}
        self.fail_focus = False

    def handle(self, method, params):
        if method == "session.snapshot":
            return {"snapshot": self.snapshot}
        target = params["target"]
        if method == "agent.read":
            text = self.texts.get(target, screen())
            if isinstance(text, list):
                text = text.pop(0)
            return {"read": {"pane_id": target, "text": text}} if text is not None else {}
        if method == "agent.get":
            agent = next(a.copy() for a in self.snapshot["agents"] if a["pane_id"] == target)
            agent["agent_status"] = self.refreshed_states.get(target, agent["agent_status"])
            return {"agent": agent}
        if method == "agent.focus":
            return {} if not self.fail_focus else None
        raise AssertionError(method)


class AttentionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ha-")
        self.addCleanup(self.tmp.cleanup)
        self.server = Server(Path(self.tmp.name) / "sock")
        self.server.__enter__()
        self.addCleanup(self.server.__exit__, None, None, None)
        self.server.snapshot = {
            "workspaces": [{"workspace_id": f"w{i}", "label": f"name {i}"} for i in range(1, 5)],
            "tabs": [{"workspace_id": f"w{i}", "tab_id": f"w{i}:t1", "label": "tab"} for i in range(1, 5)],
            "agents": [self.agent(i) for i in range(1, 5)],
            "focused_workspace_id": "w4",
        }
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}
        self.env.update(HERDR_SOCKET_PATH=str(self.server.path), HERDR_ACTIVE_WORKSPACE_ID="w1", HERDR_WORKSPACE_ID="w3")

    @staticmethod
    def agent(i, state="idle", kind="claude", suffix="1"):
        return {"workspace_id": f"w{i}", "tab_id": f"w{i}:t1", "pane_id": f"w{i}:p{suffix}", "agent": kind, "agent_status": state}

    def run_command(self, *args, env=None):
        return subprocess.run([str(HELPER), *args], env=env or self.env, text=True, capture_output=True, timeout=10)

    def selected(self, *args):
        result = self.run_command(*args, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["data"]["selected"]

    def test_direction_wrap_context_and_mixed_workspace(self):
        self.server.snapshot["agents"][1]["agent_status"] = "working"
        self.server.snapshot["agents"].append(self.agent(2, "blocked", suffix="2"))
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w2:p2")
        self.server.snapshot["agents"][1]["agent_status"] = "idle"
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w2:p2")
        self.assertEqual(self.selected("previous")["pane"]["pane_id"], "w4:p1")
        del self.env["HERDR_ACTIVE_WORKSPACE_ID"]
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w4:p1")

    def test_busy_footer_and_old_transcript(self):
        for footer in ("⏵⏵ bypass permissions on · 2 shells", "⏵⏵ bypass permissions on · 1 background agent"):
            with self.subTest(footer=footer):
                self.server.texts["w2:p1"] = screen(footer)
                self.assertEqual(self.selected("next")["pane"]["pane_id"], "w3:p1")
        self.server.texts["w2:p1"] = screen(history="✻ done · 2 shells still running")
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w2:p1")
        self.server.texts["w2:p1"] = screen("⏵⏵ bypass permissions on · 2 tasks completed")
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w2:p1")
        self.server.texts["w2:p1"] = screen("⏵⏵ bypass permissions on · 0 shells")
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w2:p1")
        self.server.texts["w2:p1"] = screen(history="custom active")
        self.assertEqual(self.selected("next", "--claude-busy-pattern", "custom active")["pane"]["pane_id"], "w2:p1")
        self.server.texts["w2:p1"] = screen(above="Waiting for 2 background agents to finish")
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w3:p1")

    def test_blocked_unreadable_and_overrides(self):
        self.server.texts["w2:p1"] = screen("⏵⏵ bypass permissions on · 2 shells")
        self.server.snapshot["agents"][1]["agent_status"] = "blocked"
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w2:p1")
        self.server.snapshot["agents"][1]["agent_status"] = "idle"
        self.assertEqual(self.selected("next", "--include-busy-claude")["pane"]["pane_id"], "w2:p1")
        self.server.texts["w2:p1"] = None
        result = self.run_command("next", "--json")
        self.assertEqual(json.loads(result.stdout)["data"]["selected"]["reason"], "unverified")
        self.assertIn("could not be verified", result.stderr)
        self.server.texts["w2:p1"] = screen("custom active")
        self.assertEqual(self.selected("next", "--claude-busy-pattern", "custom active")["pane"]["pane_id"], "w3:p1")
        self.assertEqual(self.selected("next", "--states", "blocked"), None)

    def test_refresh_no_target_list_and_errors(self):
        self.server.texts["w2:p1"] = [screen(), screen("⏵⏵ bypass permissions on · 1 shell")]
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w3:p1")
        del self.server.texts["w2:p1"]
        self.server.refreshed_states["w2:p1"] = "working"
        self.assertEqual(self.selected("next")["pane"]["pane_id"], "w3:p1")
        for agent in self.server.snapshot["agents"][1:]:
            agent["agent_status"] = "working"
        self.assertIsNone(self.selected("next"))
        self.server.snapshot["workspaces"][1]["label"] = "danger\x1b\n"
        result = self.run_command("list")
        self.assertIn('"danger\\u001b\\n"', result.stdout)
        self.assertNotIn("\x1b", result.stdout)
        result = self.run_command("list", "--json")
        self.assertTrue(json.loads(result.stdout)["ok"])
        self.assertEqual(len(json.loads(result.stdout)["data"]["decisions"]), 4)
        for args in (("next", "--states", "wrong"), ("next", "--claude-busy-pattern", "["), ("invalid",)):
            result = self.run_command(*args, "--json")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertFalse(json.loads(result.stderr)["ok"])
        self.server.snapshot["agents"][1]["agent_status"] = "blocked"
        self.server.refreshed_states.clear()
        self.server.fail_focus = True
        result = self.run_command("next", "--json")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
