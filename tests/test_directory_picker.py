"""Directory ordering and shell navigation checks; no interactive UI required."""

import importlib.machinery
import importlib.util
import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "private_dot_config/my-scripts/bin/executable_dir-picker"
loader = importlib.machinery.SourceFileLoader("directory_picker", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
picker = importlib.util.module_from_spec(spec)
loader.exec_module(picker)


class DirectoryPickerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.command = self.bin / "dir-picker"
        shutil.copyfile(SOURCE, self.command)
        self.command.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}"}
        # Make noninteractive fzf tests independent of the user's UI options.
        self.env.pop("FZF_DEFAULT_OPTS_FILE", None)
        self.env["FZF_DEFAULT_OPTS"] = ""

    def run_picker(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(self.command), *args], cwd=self.data,
            env=env or self.env, capture_output=True, timeout=10,
        )

    def test_birth_order_is_independent_of_modification_time(self):
        older = self.data / "older"
        older.mkdir()
        time.sleep(0.02)
        newer = self.data / "newer"
        newer.mkdir()
        os.utime(older, ns=(2_000_000_000_000_000_000,) * 2)
        birth = picker.linux_birth_times([str(older), str(newer)])
        if not birth and picker.native_birth_ns(older.stat()) is None:
            self.skipTest("filesystem/platform does not expose birth timestamps")
        result = self.run_picker("--list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [str(self.root), str(newer), str(older)])

    def test_fallback_order_ties_and_inclusion(self):
        for name in ["a", "b", ".hidden"]:
            directory = self.data / name
            directory.mkdir()
            os.utime(directory, ns=(1_000_000_000,) * 2)
        link = self.data / "link"
        link.symlink_to(self.data / "a", target_is_directory=True)
        os.utime(link, ns=(2_000_000_000,) * 2, follow_symlinks=False)
        (self.data / "plain-file").touch()
        (self.data / "file-link").symlink_to(self.data / "plain-file")
        (self.data / "broken-link").symlink_to(self.data / "absent")
        with patch.object(picker, "native_birth_ns", return_value=None), \
                patch.object(picker, "linux_birth_times", return_value={}):
            labels = [label for label, _ in picker.directory_choices(self.data)]
        self.assertEqual(labels, ["../", "link/", ".hidden/", "a/", "b/"])

    def test_list_json_null_and_explicit_root_preserve_names(self):
        unusual = self.data / " 한글 space\ttab\nnewline\n"
        unusual.mkdir()
        result = self.run_picker("--list", "--json", str(self.data))
        expected = [str(self.root), str(unusual)]
        self.assertEqual(json.loads(result.stdout), expected)
        result = self.run_picker("--list", "--null")
        self.assertEqual(result.stdout, b"".join(os.fsencode(path) + b"\0" for path in expected))

    def test_invalid_root_and_missing_fzf(self):
        invalid = self.run_picker(str(self.data / "missing"))
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, b"")
        missing = self.run_picker(env={**self.env, "PATH": str(self.bin)})
        self.assertEqual(missing.returncode, 127)
        self.assertIn(b"fzf is required", missing.stderr)
        self.assertEqual(missing.stdout, b"")
        listing = self.run_picker("--list", "--json", env={**self.env, "PATH": str(self.bin)})
        self.assertEqual(listing.returncode, 0, listing.stderr)

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_real_fzf_selection_and_no_match(self):
        target = self.data / "new project"
        target.mkdir()
        env = {**self.env, "FZF_DEFAULT_OPTS": "--filter=project --multi --print-query"}
        result = self.run_picker("--json", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), str(target))
        result = self.run_picker(env={**self.env, "FZF_DEFAULT_OPTS": "--filter=absent"})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_terminal_selection_preserves_order_while_filtering(self):
        for name in ["a-project", "z-project"]:
            (self.data / name).mkdir()
            time.sleep(0.02)
        output = self.root / "selection.json"
        pid, terminal = pty.fork()
        if pid == 0:
            os.chdir(self.data)
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT, 0o600)
            os.dup2(descriptor, 1)
            os.close(descriptor)
            # A user's --tac must not reverse the picker's time ordering.
            env = {**self.env, "TERM": "xterm-256color", "FZF_DEFAULT_OPTS": "--tac"}
            os.execve(sys.executable, [sys.executable, str(self.command), "--json"], env)
        fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
        rendered = b""
        query_sent = None
        accepted = False
        exited = False
        deadline = time.monotonic() + 8
        try:
            while time.monotonic() < deadline:
                if select.select([terminal], [], [], 0.05)[0]:
                    try:
                        chunk = os.read(terminal, 65536)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        break
                    rendered += chunk
                    if b"\x1b[6n" in chunk:
                        os.write(terminal, b"\x1b[1;1R")
                if query_sent is None and b"z-project" in rendered:
                    os.write(terminal, b"project")
                    query_sent = time.monotonic()
                elif query_sent is not None and not accepted and time.monotonic() - query_sent > 0.3:
                    os.write(terminal, b"\r")
                    accepted = True
                waited, status = os.waitpid(pid, os.WNOHANG)
                if waited:
                    exited = True
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0, rendered)
                    break
            if not exited:
                waited, status = os.waitpid(pid, os.WNOHANG)
                exited = bool(waited)
                self.assertTrue(exited, "fzf did not exit after terminal selection")
                self.assertEqual(os.waitstatus_to_exitcode(status), 0, rendered)
        finally:
            if not exited:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(terminal)
        self.assertEqual(json.loads(output.read_text()), str(self.data / "z-project"))

    def fake_fzf(self, status=0):
        """A picker boundary fixture for shell framing and cancellation tests."""
        command = self.bin / "fzf"
        command.write_text(
            f"#!{sys.executable}\nimport os, sys\n"
            "labels = sys.stdin.buffer.read().split(b'\\0')\n"
            f"if {status}: sys.exit({status})\n"
            "label = os.fsencode(os.environ['PICK_LABEL'])\n"
            "assert label in labels\n"
            "sys.stdout.buffer.write(label + b'\\0')\n"
        )
        command.chmod(0o755)

    def run_shell(self, shell, direct=False):
        if shell == "nu":
            code = (
                "def ezam [] {}; "
                f"source {json.dumps(str(REPO / 'private_dot_config/nushell/alias.nu'))}; "
                f"c{' $env.DIRECT_PATH' if direct else ''}; $env.PWD | to json --raw"
            )
            command = ["nu", "--no-config-file", "-c", code]
        else:
            code = (
                '_cached_source() { :; }; '
                'source "$ALIASES_SOURCE"; my-list-long() { :; }; '
                f"eval 'c{' \"$DIRECT_PATH\"' if direct else ''}'; "
                'python3 -c \'import json, os; print(json.dumps(os.getcwd()))\''
            )
            command = ["zsh", "-f", "-c", code]
        return subprocess.run(command, cwd=self.data, env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_shell_selection_direct_navigation_parent_and_cancellation(self):
        target = self.data / " 한글 space\ttab\nnewline\n"
        target.mkdir()
        self.env["ALIASES_SOURCE"] = str(REPO / "private_dot_config/my-scripts/zsh/aliases.zsh")
        self.env["DIRECT_PATH"] = str(target)
        self.env["PICK_LABEL"] = target.name + "/"
        for shell in ["nu", "zsh"]:
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                self.fake_fzf()
                selected = self.run_shell(shell)
                self.assertEqual(selected.returncode, 0, selected.stderr)
                self.assertEqual(json.loads(selected.stdout), str(target))
                direct = self.run_shell(shell, direct=True)
                self.assertEqual(direct.returncode, 0, direct.stderr)
                self.assertEqual(json.loads(direct.stdout), str(target))
                self.env["PICK_LABEL"] = "../"
                parent = self.run_shell(shell)
                self.assertEqual(parent.returncode, 0, parent.stderr)
                self.assertEqual(json.loads(parent.stdout), str(self.root))
                self.env["PICK_LABEL"] = target.name + "/"
                for status in [1, 130]:
                    self.fake_fzf(status)
                    cancelled = self.run_shell(shell)
                    self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
                    self.assertEqual(json.loads(cancelled.stdout), str(self.data))


if __name__ == "__main__":
    unittest.main()
