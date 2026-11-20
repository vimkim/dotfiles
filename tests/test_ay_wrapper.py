"""Verify the ay exec wrapper launches agy with permission bypass."""

import json
import os
from pathlib import Path
import pty
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "private_dot_local/bin/executable_ay"
STUB = r'''#!/usr/bin/env python3
import json
import os
import sys

if os.isatty(0):
    with open(os.environ["AY_LOG"], "w", encoding="utf-8") as handle:
        json.dump(
            {
                "args": sys.argv[1:],
                "pid": os.getpid(),
                "pgrp": os.getpgrp(),
                "tty": os.ttyname(0),
            },
            handle,
        )
    sys.exit(0)

print(json.dumps({"args": sys.argv[1:], "input": sys.stdin.read()}))
sys.exit(7)
'''


class AyWrapperTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="ay-wrapper-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.log = self.root / "log.json"
        stub = self.root / "agy"
        stub.write_text(
            STUB.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1),
            encoding="utf-8",
        )
        stub.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
            "AY_LOG": str(self.log),
        }

    def test_script_is_executable(self) -> None:
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_exec_replaces_wrapper_and_preserves_tty(self) -> None:
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        proc = subprocess.Popen(
            [str(SCRIPT)],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=self.env,
            start_new_session=True,
        )
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        self.assertEqual(proc.wait(timeout=4), 0)
        launch = json.loads(self.log.read_text(encoding="utf-8"))
        self.assertEqual(launch["pid"], proc.pid)
        self.assertEqual(launch["pgrp"], proc.pid)
        self.assertEqual(launch["tty"], os.ttyname(slave))
        self.assertEqual(launch["args"], ["--dangerously-skip-permissions"])

    def test_prepends_bypass_flag_and_preserves_args_stdin_and_exit_status(self) -> None:
        args = ["-p", "two words", "", "한글", "--", "--flag"]
        result = subprocess.run(
            [str(SCRIPT), *args],
            input="piped input",
            env=self.env,
            text=True,
            capture_output=True,
            timeout=4,
            check=False,
        )
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            json.loads(result.stdout),
            {
                "args": ["--dangerously-skip-permissions", *args],
                "input": "piped input",
            },
        )


if __name__ == "__main__":
    unittest.main()
