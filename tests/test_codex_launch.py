"""Keep native Codex visible to terminal multiplexers, including old shell aliases."""

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


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "private_dot_config/my-scripts/bin/executable_codex-safe"
STUB = r'''#!/usr/bin/env python3
import json,os,sys,termios,tty
def log(**value):
    with open(os.environ['CODEX_LAUNCH_LOG'], 'a') as handle:
        handle.write(json.dumps(value) + '\n')
log(args=sys.argv[1:], pid=os.getpid(), group=os.getpgrp(),
    terminal=os.ttyname(0) if os.isatty(0) else None)
if not os.isatty(0):
    print(json.dumps({'args':sys.argv[1:], 'input':sys.stdin.read()}))
    sys.exit(5)
original = termios.tcgetattr(0)
try:
    tty.setraw(0)
    log(ready=True)
    while True:
        data = os.read(0, 65536)
        if not data:
            break
        log(keys=data.hex())
        if b'\x03' in data:
            sys.exit(7)
finally:
    termios.tcsetattr(0, termios.TCSANOW, original)
'''


class CodexLaunchTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="codex-launch-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.log = self.root / "log.jsonl"
        stub = self.root / "codex"
        stub.write_text(STUB.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
        stub.chmod(0o755)
        self.launcher = self.root / "codex-safe"
        shutil.copyfile(SCRIPT, self.launcher)
        self.launcher.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
                    "CODEX_LAUNCH_LOG": str(self.log), "TERM": "xterm-256color"}

    def rows(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=4)

    def test_interactive_launch_keeps_the_pane_process_group_terminal_and_keys(self):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        original = termios.tcgetattr(slave)
        self.proc = subprocess.Popen([str(self.launcher), "--profile", "dotfiles"],
                                     stdin=slave, stdout=slave, stderr=slave,
                                     env=self.env, start_new_session=True)
        self.addCleanup(self.stop)
        deadline = time.monotonic() + 4
        while not any(row.get("ready") for row in self.rows()):
            if time.monotonic() >= deadline:
                self.fail("Codex stand-in did not reach its input loop")
            if select.select([master], [], [], .02)[0]:
                os.read(master, 65536)
        launch = self.rows()[0]
        self.assertEqual(launch["pid"], self.proc.pid, "Codex must replace the launcher")
        self.assertEqual(launch["group"], self.proc.pid, "Codex must stay in the pane's process group")
        self.assertEqual(launch["terminal"], os.ttyname(slave), "Codex must use the pane's terminal")
        self.assertEqual(launch["args"], ["--profile", "dotfiles"])
        keys = b"\x18c\x1b[A\x03"
        os.write(master, keys)
        self.assertEqual(self.proc.wait(timeout=4), 7)
        self.assertEqual(b"".join(bytes.fromhex(row["keys"]) for row in self.rows() if "keys" in row), keys)
        self.assertEqual(termios.tcgetattr(slave), original)

    def test_automation_preserves_arguments_input_and_exit_status(self):
        args = ["--profile", "dotfiles", "exec", "--json", "a prompt", "", "한글"]
        result = subprocess.run([str(self.launcher), *args], input="piped input",
                                env=self.env, text=True, capture_output=True, timeout=4)
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"args": args, "input": "piped input"})
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
