"""Verify shortcut protection with real pseudo-terminals and a disposable CLI."""

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "private_dot_config/my-scripts/bin/executable_codex-safe"
loader = importlib.machinery.SourceFileLoader("codex_safe", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
safe = importlib.util.module_from_spec(spec)
loader.exec_module(safe)

STUB = r'''#!/usr/bin/env python3
import json,os,signal,sys,termios,tty
def log(**value):
    with open(os.environ['SHORTCUT_LOG'],'a') as f:
        f.write(json.dumps(value)+'\n')
log(args=sys.argv[1:])
if not os.isatty(0) or '--help' in sys.argv or 'exec' in sys.argv:
    print(json.dumps({'args':sys.argv[1:], 'input':sys.stdin.read() if not os.isatty(0) else ''}))
    sys.exit(5)
original=termios.tcgetattr(0)
tty.setraw(0)
signal.signal(signal.SIGWINCH, lambda *_: log(size=list(termios.tcgetwinsize(0))))
log(ready=True, pid=os.getpid(), size=list(termios.tcgetwinsize(0)))
while True:
    data=os.read(0,65536)
    if not data: break
    log(keys=data.hex())
    if data == b'\x1a':
        os.kill(os.getpid(),signal.SIGSTOP)
        log(resumed=True)
    if data == b'\x03':
        if os.environ.get('GRACEFUL_EXIT'):
            import time
            termios.tcsetattr(0,termios.TCSANOW,original)
            time.sleep(.5)
        sys.exit(7)
'''


class CodexSafeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "log.jsonl"
        stub = self.root / "codex"
        stub.write_text(STUB)
        stub.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
                    "SHORTCUT_LOG": str(self.log), "TERM": "xterm-256color"}

    def rows(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def wait_for(self, predicate):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            rows = self.rows()
            if predicate(rows):
                return rows
            self.drain()
        self.fail("Timed out waiting for terminal events: " + repr(self.rows()))

    def drain(self):
        if select.select([self.master], [], [], 0.02)[0]:
            try:
                os.read(self.master, 65536)
            except OSError:
                pass

    def launch(self, *args):
        self.master, self.slave = pty.openpty()
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        termios.tcsetwinsize(self.slave, (40, 120))
        self.original = termios.tcgetattr(self.slave)
        self.proc = subprocess.Popen([sys.executable, str(SCRIPT), *args],
                                     stdin=self.slave, stdout=self.slave, stderr=self.slave,
                                     env=self.env, start_new_session=True)
        self.addCleanup(self.stop)
        return self.wait_for(lambda rows: any(row.get("ready") for row in rows))

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                for row in self.rows():
                    if row.get("pid"):
                        try:
                            os.killpg(row["pid"], signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                self.proc.kill()
                self.proc.wait(timeout=3)

    def keys(self):
        return b"".join(bytes.fromhex(row["keys"]) for row in self.rows() if "keys" in row)

    def test_single_ctrl_c_is_ignored_double_quits_and_restores_terminal(self):
        self.launch("--profile", "dotfiles")
        os.write(self.master, b"\x03")
        time.sleep(0.12)
        self.assertIsNone(self.proc.poll())
        self.assertEqual(self.keys(), b"")
        os.write(self.master, b"\x03")
        self.assertEqual(self.proc.wait(timeout=4), 7)
        self.assertEqual(termios.tcgetattr(self.slave), self.original)

    def test_cancel_chord_preserves_session_and_does_not_arm_quit(self):
        rows = self.launch()
        self.assertIn('tui.keymap.chat.interrupt_turn="leader c"', rows[0]["args"])
        os.write(self.master, b"\x18\x03")
        self.wait_for(lambda _: self.keys() == b"\x18c")
        os.write(self.master, b"\x03")
        time.sleep(0.12)
        self.assertIsNone(self.proc.poll())
        self.assertEqual(self.keys(), b"\x18c")

    def test_quit_does_not_signal_child_after_it_restores_its_terminal(self):
        self.env['GRACEFUL_EXIT'] = '1'
        self.launch()
        os.write(self.master, b"\x03\x03")
        self.assertEqual(self.proc.wait(timeout=4), 7)
        self.assertEqual(termios.tcgetattr(self.slave), self.original)

    def test_escape_arrows_and_split_kitty_chord(self):
        self.launch()
        os.write(self.master, b"\x1b")
        self.wait_for(lambda _: self.keys() == b"\x1b")
        os.write(self.master, b"\x1b[A\x1b[120;5u\x1b[99;")
        time.sleep(0.01)
        os.write(self.master, b"5u")
        self.wait_for(lambda _: self.keys() == b"\x1b\x1b[A\x18c")
        self.assertIsNone(self.proc.poll())

    def test_resize_and_termination_reach_child_and_restore_terminal(self):
        self.launch()
        termios.tcsetwinsize(self.slave, (55, 150))
        os.kill(self.proc.pid, signal.SIGWINCH)
        self.wait_for(lambda rows: any(row.get("size") == [55, 150] for row in rows))
        self.proc.terminate()
        self.assertEqual(self.proc.wait(timeout=4), 143)
        self.assertEqual(termios.tcgetattr(self.slave), self.original)

    def test_automation_preserves_arguments_input_and_exit_status(self):
        args = ["--profile", "dotfiles", "exec", "--json", "a prompt"]
        result = subprocess.run([sys.executable, str(SCRIPT), *args], input="piped input",
                                env=self.env, text=True, capture_output=True, timeout=4)
        self.assertEqual(result.returncode, 5)
        self.assertEqual(json.loads(result.stdout), {"args": args, "input": "piped input"})
        self.assertEqual(result.stderr, "")

    def test_suspended_child_restores_terminal_until_resumed(self):
        self.launch()
        os.write(self.master, b"\x1a")
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            waited, status = os.waitpid(self.proc.pid, os.WNOHANG | os.WUNTRACED)
            if waited and os.WIFSTOPPED(status):
                break
            self.drain()
        else:
            self.fail("The wrapper did not suspend with its child.")
        try:
            self.assertEqual(termios.tcgetattr(self.slave), self.original)
        finally:
            os.kill(self.proc.pid, signal.SIGCONT)
        self.wait_for(lambda rows: any(row.get("resumed") for row in rows))
        os.write(self.master, b"\x03\x03")
        self.assertEqual(self.proc.wait(timeout=4), 7)
        self.assertEqual(termios.tcgetattr(self.slave), self.original)

    def test_terminal_exec_also_bypasses_translation(self):
        self.master, self.slave = pty.openpty()
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        self.proc = subprocess.Popen([sys.executable, str(SCRIPT), "exec", "--json", "prompt"],
                                     stdin=self.slave, stdout=self.slave, stderr=self.slave,
                                     env=self.env)
        self.addCleanup(self.stop)
        self.assertEqual(self.proc.wait(timeout=4), 5)
        self.assertEqual(self.rows()[0]["args"], ["exec", "--json", "prompt"])


class InputProtocolTest(unittest.TestCase):
    def test_slow_ctrl_c_and_intervening_input_do_not_confirm_quit(self):
        keys = safe.Shortcuts()
        self.assertEqual(keys.feed(b"\x03", 0), b"")
        self.assertEqual(keys.feed(b"\x03", 2), b"")
        self.assertFalse(keys.quitting)
        self.assertEqual(keys.feed(b"text", 2.1), b"text")
        self.assertEqual(keys.feed(b"\x03", 2.2), b"")
        self.assertFalse(keys.quitting)

    def test_bracketed_paste_never_interprets_embedded_controls(self):
        keys = safe.Shortcuts()
        pasted = b"\x1b[200~example\x18\x03\x03\x1b[201~"
        result = b"".join(keys.feed(bytes([byte]), i / 1000) for i, byte in enumerate(pasted))
        self.assertEqual(result, pasted)
        self.assertFalse(keys.quitting)

    def test_kitty_releases_and_repeats_do_not_confirm_quit(self):
        keys = safe.Shortcuts()
        self.assertEqual(keys.feed(b"\x1b[99;5u", 0), b"")
        self.assertEqual(keys.feed(b"\x1b[99;5:2u\x1b[99;5:3u", .1), b"")
        self.assertFalse(keys.quitting)
        self.assertEqual(keys.feed(b"\x1b[99;5u", .2), b"\x03")
        self.assertTrue(keys.quitting)

    def test_modify_other_keys_cancel_chord(self):
        keys = safe.Shortcuts()
        self.assertEqual(keys.feed(b"\x1b[27;5;120~\x1b[27;5;99~", 0), b"\x18c")

    def test_kitty_lock_flags_and_modifier_release_preserve_chord(self):
        keys = safe.Shortcuts()
        release = b"\x1b[57442;65:3u"
        press = b"\x1b[57442;69u"
        self.assertEqual(keys.feed(b"\x1b[120;69u" + release + press + b"\x1b[99;69u", 0),
                         b"\x18" + release + press + b"c")
        self.assertFalse(keys.quitting)

    def test_kitty_base_layout_identifies_control_key(self):
        keys = safe.Shortcuts()
        self.assertEqual(keys.feed(b"\x1b[1095::120;5u\x1b[1089::99;5u", 0), b"\x18c")

    def test_command_flags_are_not_mistaken_for_subcommands(self):
        self.assertTrue(safe.interactive(["--profile", "exec"]))
        self.assertTrue(safe.interactive(["resume", "--last"]))
        self.assertTrue(safe.interactive(["--", "exec"]))
        self.assertFalse(safe.interactive(["-c", 'model="test"', "exec", "prompt"]))
        self.assertFalse(safe.interactive(["--help"]))
        self.assertFalse(safe.interactive(["resume", "--last", "--help"]))


if __name__ == "__main__":
    unittest.main()
