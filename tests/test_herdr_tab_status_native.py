"""Opt-in contract test against an isolated installed Herdr server.

Run with HERDR_NATIVE_TESTS=1 python3 -B -m unittest
tests.test_herdr_tab_status_native -v (on one command line).
"""

import os
import runpy
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path


HELPER = (
    Path(__file__).resolve().parents[1]
    / "private_dot_local/bin/executable_herdr-tab-status"
)
HERDR = shutil.which("herdr")


@unittest.skipUnless(
    HERDR and os.environ.get("HERDR_NATIVE_TESTS") == "1",
    "requires herdr and HERDR_NATIVE_TESTS=1",
)
class HerdrTabStatusNativeTest(unittest.TestCase):
    def setUp(self):
        # Unix socket paths, including Herdr's session suffix, must fit sun_path.
        self.temporary = tempfile.TemporaryDirectory(prefix="ht-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        config = self.root / "config.toml"
        config.write_text(
            'onboarding = false\n'
            '[terminal]\ndefault_shell = "/bin/sh"\n'
            '[experimental]\nallow_nested = true\n'
            '[update]\nversion_check = false\nmanifest_check = false\n'
        )
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("HERDR_")
        }
        environment.update(
            HERDR_CONFIG_PATH=str(config),
            XDG_CONFIG_HOME=str(self.root / "config"),
            XDG_CACHE_HOME=str(self.root / "cache"),
            XDG_STATE_HOME=str(self.root / "state"),
        )
        self.module = runpy.run_path(str(HELPER))
        self.socket_path = None
        self.log = (self.root / "server.log").open("w+")
        self.addCleanup(self.log.close)
        session_name = "ht-" + uuid.uuid4().hex[:8]
        self.server = subprocess.Popen(
            [HERDR, "--session", session_name, "server"],
            env=environment,
            cwd=self.root,
            stdin=subprocess.DEVNULL,
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )
        self.addCleanup(self.stop_server)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            for path in self.root.rglob("*.sock"):
                if path.is_socket() and "client" not in path.name:
                    self.socket_path = str(path)
                    try:
                        self.request("session.snapshot", {})
                        self.directory = self.root / "journal"
                        self.directory.mkdir()
                        return
                    except (OSError, RuntimeError):
                        self.socket_path = None
            if self.server.poll() is not None:
                break
            time.sleep(0.05)
        self.log.seek(0)
        self.fail("Isolated server failed to start: " + self.log.read())

    def request(self, method, params):
        return self.module["request"](self.socket_path, method, params)

    def stop_server(self):
        if self.server.poll() is None:
            try:
                if self.socket_path:
                    self.request("server.stop", {})
                self.server.wait(timeout=5)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                self.server.terminate()
                self.server.wait(timeout=5)

    def update(self):
        return self.module["Updater"](self.socket_path, self.directory).update()

    def tabs(self, workspace_id):
        snapshot = self.request("session.snapshot", {})["snapshot"]
        return [tab for tab in snapshot["tabs"] if tab["workspace_id"] == workspace_id]

    def test_native_reorder_and_close_use_positions_instead_of_creation_numbers(self):
        created = self.request("workspace.create", {"label": "test", "focus": False})
        workspace_id = created["workspace"]["workspace_id"]
        first = created["tab"]["tab_id"]
        second = self.request(
            "tab.create",
            {"workspace_id": workspace_id, "label": "review", "focus": False},
        )["tab"]["tab_id"]
        third = self.request(
            "tab.create", {"workspace_id": workspace_id, "focus": False}
        )["tab"]["tab_id"]
        self.update()

        moved = self.request("tab.move", {"tab_id": third, "insert_index": 0})["tabs"]
        self.assertEqual([tab["tab_id"] for tab in moved], [third, first, second])
        self.assertEqual([tab["number"] for tab in moved], [3, 1, 2])
        self.assertEqual(
            [tab["tab_id"] for tab in self.tabs(workspace_id)], [third, first, second]
        )
        self.update()
        self.assertEqual(
            [tab["label"] for tab in self.tabs(workspace_id)],
            ["1 [— shell]", "2 [— shell]", "3 review [— shell]"],
        )

        self.request("tab.close", {"tab_id": first})
        self.update()
        remaining = self.tabs(workspace_id)
        self.assertEqual([tab["number"] for tab in remaining], [3, 2])
        self.assertEqual(
            [tab["label"] for tab in remaining], ["1 [— shell]", "2 review [— shell]"]
        )
        self.module["Updater"](self.socket_path, self.directory).restore()
        self.assertEqual(
            [tab["label"] for tab in self.tabs(workspace_id)], ["3", "review"]
        )


if __name__ == "__main__":
    unittest.main()
