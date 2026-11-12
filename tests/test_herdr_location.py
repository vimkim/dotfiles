import base64
import os
import pty
import select
import signal
import subprocess
import termios
import tempfile
import time
import unittest
from pathlib import Path

from tests.test_herdr_tab_status import HerdrServer


HELPER = Path(__file__).resolve().parents[1] / "private_dot_local/bin/executable_herdr-location"


class HerdrLocationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hl-")
        self.addCleanup(self.temporary.cleanup)
        self.server = HerdrServer(Path(self.temporary.name) / "herdr.sock")
        self.server.__enter__()
        self.addCleanup(self.server.__exit__, None, None, None)
        self.server.snapshot = {
            "workspaces": [
                {"workspace_id": "w1", "label": "한글\n\x1b[31m", "focused": False},
                {"workspace_id": "w2", "label": "other", "focused": True},
            ],
            "tabs": [
                {"tab_id": "w1:t7", "workspace_id": "w1", "label": "검토\x9bX\u2028", "focused": False},
                {"tab_id": "w2:t1", "workspace_id": "w2", "label": "other tab", "focused": True},
            ],
            "panes": [
                {"pane_id": "w1:p4", "tab_id": "w1:t7", "workspace_id": "w1", "focused": False},
                {"pane_id": "w2:p1", "tab_id": "w2:t1", "workspace_id": "w2", "focused": True},
            ],
            "agents": [],
        }
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("HERDR_")}
        self.env.update(HERDR_SOCKET_PATH=str(self.server.path), HERDR_ACTIVE_PANE_ID="w1:p4", HERDR_PANE_ID="w2:p1")
        self.reference = '"한글\\n\\u001b[31m" (w1), tab "검토\\u009bX\\u2028" (w1:t7), pane w1:p4'

    def command(self, env=None):
        return subprocess.run([str(HELPER)], env=env or self.env, text=True, capture_output=True, timeout=5)

    def run_popup(self, key, env=None, expected="q/Esc: close"):
        master, slave = pty.openpty()
        before = termios.tcgetattr(slave)
        process = subprocess.Popen([str(HELPER), "--popup"], env=env or self.env,
                                   stdin=slave, stdout=slave, stderr=slave, close_fds=True)
        output = bytearray()
        try:
            deadline = time.monotonic() + 5
            while expected.encode() not in output and time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    output.extend(os.read(master, 65536))
            self.assertIn(expected.encode(), output)
            if key == b"interrupt":
                process.send_signal(signal.SIGINT)
            else:
                os.write(master, key)
            process.wait(timeout=5)
            while select.select([master], [], [], 0)[0]:
                output.extend(os.read(master, 65536))
            self.assertEqual(termios.tcgetattr(slave), before)
            return process.returncode, bytes(output)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            os.close(slave)

    def test_active_pane_wins_over_inherited_pane_and_global_focus(self):
        result = self.command()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.reference + "\n")
        self.assertEqual([request["method"] for request in self.server.requests], ["session.snapshot"])

    def test_inherited_pane_fallback(self):
        env = self.env.copy()
        del env["HERDR_ACTIVE_PANE_ID"]
        result = self.command(env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '"other" (w2), tab "other tab" (w2:t1), pane w2:p1\n')

    def test_popup_copy_options_and_cancel_restore_terminal(self):
        for key, value in [(b"c", self.reference), (b"\r", self.reference),
                           (b"p", "w1:p4"), (b"t", "w1:t7"), (b"w", "w1")]:
            with self.subTest(key=key):
                code, output = self.run_popup(key)
                self.assertEqual(code, 0)
                self.assertIn(b"\x1b]52;c;" + base64.b64encode(value.encode()) + b"\x07", output)
                self.assertNotIn(b"\x1b[31m", output)
        for key in (b"q", b"\x1b"):
            code, output = self.run_popup(key)
            self.assertEqual(code, 0)
            self.assertNotIn(b"\x1b]52;", output)

    def test_invalid_key_waits_until_copy(self):
        code, output = self.run_popup(b"z" + b"t")
        self.assertEqual(code, 0)
        self.assertIn(b"\x1b]52;c;dzE6dDc=\x07", output)

    def test_missing_stale_or_inconsistent_context_fails_without_copy(self):
        original = self.server.snapshot.copy()
        original["panes"] = [pane.copy() for pane in original["panes"]]
        for change in ("missing_socket", "missing_pane", "stale", "inconsistent", "unavailable", "missing_data"):
            with self.subTest(change=change):
                self.server.snapshot = {**original, "panes": [pane.copy() for pane in original["panes"]]}
                env = self.env.copy()
                if change == "missing_socket":
                    del env["HERDR_SOCKET_PATH"]
                elif change == "missing_pane":
                    del env["HERDR_ACTIVE_PANE_ID"]
                    del env["HERDR_PANE_ID"]
                elif change == "stale":
                    env["HERDR_ACTIVE_PANE_ID"] = "w1:p99"
                elif change == "inconsistent":
                    self.server.snapshot["panes"][0]["workspace_id"] = "w2"
                elif change == "unavailable":
                    env["HERDR_SOCKET_PATH"] = str(Path(self.temporary.name) / "missing.sock")
                else:
                    del self.server.snapshot["tabs"]
                result = self.command(env)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                code, output = self.run_popup(b"cq", env, expected="Press q")
                self.assertNotEqual(code, 0)
                self.assertNotIn(b"\x1b]52;", output)

    def test_interrupt_restores_terminal(self):
        code, output = self.run_popup(b"interrupt")
        self.assertEqual(code, 130)
        self.assertNotIn(b"\x1b]52;", output)


if __name__ == "__main__":
    unittest.main()
