#!/usr/bin/env python3

import base64
import fcntl
import os
import pty
import subprocess
import tempfile
import termios
import unittest
from pathlib import Path

NO_BROWSER = (
    Path(__file__).resolve().parents[1] / "private_dot_local/bin/executable_no-browser"
)
URL = "https://example.com/a?b=c&d=e"


class NoBrowserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = tempfile.TemporaryDirectory()
        bin_dir = Path(self.cache.name) / "bin"
        bin_dir.mkdir()
        self.herdr_args = Path(self.cache.name) / "herdr-args"
        fake_herdr = bin_dir / "herdr"
        fake_herdr.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > '{self.herdr_args}'\n")
        fake_herdr.chmod(0o755)
        self.env = {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": self.cache.name,
            "XDG_CACHE_HOME": self.cache.name,
        }

    def tearDown(self) -> None:
        self.cache.cleanup()

    def test_copies_url_to_controlling_terminal_with_osc52(self) -> None:
        # Keep the slave open in the parent, as Herdr keeps its terminal open,
        # so the sequence stays readable after the child exits.
        master, slave = pty.openpty()
        pid = os.fork()
        if pid == 0:
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            # Detach stdio from the terminal, as Herdr does for link openers.
            devnull = os.open(os.devnull, os.O_RDWR)
            for fd in (0, 1, 2):
                os.dup2(devnull, fd)
            os.close(slave)
            os.close(master)
            os.execve("/bin/sh", ["sh", str(NO_BROWSER), URL], self.env)
        _, status = os.waitpid(pid, 0)
        os.set_blocking(master, False)
        try:
            output = os.read(master, 4096)
        except BlockingIOError:
            output = b""
        os.close(master)
        os.close(slave)
        self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        encoded = base64.b64encode(URL.encode()).decode()
        self.assertIn(f"\x1b]52;c;{encoded}\x07".encode(), output)
        self.assertEqual(
            self.herdr_args.read_text().splitlines(),
            [
                "notification",
                "show",
                "📋 Copied link",
                "--body",
                URL,
                "--position",
                "bottom-right",
                "--sound",
                "none",
            ],
        )

    def test_succeeds_without_controlling_terminal(self) -> None:
        result = subprocess.run(
            ["/bin/sh", str(NO_BROWSER), URL],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            start_new_session=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("Copied URL", result.stderr)
        self.assertFalse(self.herdr_args.exists(), "no toast without a copy")
        self.assertIn(URL, (Path(self.cache.name) / "no-browser.log").read_text())


if __name__ == "__main__":
    unittest.main()
