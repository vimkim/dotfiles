"""Integration checks with real eza, shell pipes, and less in a small PTY."""

import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import tempfile
import termios
import time
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "private_dot_config/my-scripts/bin"
NAMES = ["ls-by-name", "ls-by-size", "ls-by-time", "ls-by-extension", "ls-tree", "ls-dirs", "ls-files"]
PLAIN = ["--no-user", "--no-permissions", "--no-filesize", "--no-time", "--color=never", "--icons=never"]


@unittest.skipUnless(shutil.which("eza") and shutil.which("less"), "requires eza and less")
class ListingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        shutil.copyfile(SOURCE / "executable_ls-by-name", self.bin / "ls-by-name")
        (self.bin / "ls-by-name").chmod(0o755)
        for name in NAMES[1:]:
            (self.bin / name).symlink_to((SOURCE / f"symlink_{name}").read_text().strip())
        self.data = self.root / "data"
        self.data.mkdir()
        for name, size, modified in [("a.txt", 1, 300), ("z.py", 100, 100), (".hidden", 10, 200)]:
            path = self.data / name
            path.write_text("x" * size)
            os.utime(path, (modified, modified))
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "TERM": "xterm", "LC_ALL": "C.UTF-8"}

    def run_listing(self, name, *args, path=None, env=None):
        return subprocess.run(
            [str(self.bin / name), *PLAIN, *args, str(path or self.data)],
            capture_output=True, text=True, env=env or self.env, timeout=5,
        )

    def test_sort_defaults_and_reverse(self):
        for command, expected in {
            "ls-by-name": [".hidden", "a.txt", "z.py"],
            "ls-by-size": ["z.py", ".hidden", "a.txt"],
            "ls-by-time": ["a.txt", ".hidden", "z.py"],
        }.items():
            with self.subTest(command=command):
                normal = self.run_listing(command)
                self.assertEqual(normal.returncode, 0, normal.stderr)
                self.assertEqual(normal.stdout.splitlines(), expected)
                self.assertEqual(self.run_listing(command, "--reverse").stdout.splitlines(), expected[::-1])
                self.assertEqual(self.run_listing(command, "-r").stdout.splitlines(), expected[::-1])
                self.assertEqual(self.run_listing(command, "-lr").stdout.splitlines(), expected[::-1])

    def test_extension_secondary_name_order(self):
        (self.data / "b.py").touch()
        names = self.run_listing("ls-by-extension").stdout.splitlines()
        self.assertLess(names.index("b.py"), names.index("z.py"))
        self.assertLess(names.index("z.py"), names.index("a.txt"))

    def test_global_order_and_directory_filter(self):
        (self.data / "m-dir").mkdir()
        self.assertEqual(self.run_listing("ls-by-name").stdout.splitlines(), [".hidden", "a.txt", "m-dir", "z.py"])
        self.assertEqual(self.run_listing("ls-dirs").stdout.splitlines(), ["m-dir"])
        self.assertEqual(self.run_listing("ls-files").stdout.splitlines(), [".hidden", "a.txt", "z.py"])

    def test_tree_depth_and_override(self):
        nested = self.data / "one" / "two"
        nested.mkdir(parents=True)
        (nested / "deep-file").touch()
        default = self.run_listing("ls-tree").stdout
        self.assertIn("two", default)
        self.assertNotIn("deep-file", default)
        self.assertIn("deep-file", self.run_listing("ls-tree", "--level=3").stdout)

    def test_no_truncation_and_path_with_spaces(self):
        many = self.root / "many entries"
        many.mkdir()
        for n in range(450):
            (many / f"file-{n:03}").touch()
        result = self.run_listing("ls-by-name", path=many)
        self.assertEqual(len(result.stdout.splitlines()), 450)
        self.assertIn("file-449", result.stdout)

    def test_errors_and_literal_option_filename(self):
        missing = self.run_listing("ls-by-name", path=self.root / "absent")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("absent", missing.stderr)
        (self.data / "--no-pager").touch()
        literal = subprocess.run([str(self.bin / "ls-by-name"), *PLAIN, "--", "--no-pager"],
                                 cwd=self.data, capture_output=True, text=True, env=self.env)
        self.assertEqual(literal.returncode, 0, literal.stderr)
        self.assertEqual(literal.stdout.strip(), "--no-pager")

    def test_current_directory_with_option_values_and_explicit_stdin(self):
        for options in [[], ["--color", "never"], ["--icons"], ["--sort", "size"],
                        ["-sname"], ["-I", "-r"], ["--color-scale", "age", "size"]]:
            with self.subTest(options=options):
                result = subprocess.run([str(self.bin / "ls-by-name"), *options],
                                        cwd=self.data, capture_output=True, text=True, env=self.env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("a.txt", result.stdout)
        stdin = subprocess.run([str(self.bin / "ls-by-name"), *PLAIN, "--stdin"],
                               input="z.py\na.txt\n", cwd=self.data, capture_output=True,
                               text=True, env=self.env)
        self.assertEqual(stdin.returncode, 0, stdin.stderr)
        self.assertEqual(stdin.stdout.splitlines(), ["a.txt", "z.py"])

    def test_missing_dependencies(self):
        isolated = self.root / "isolated-bin"
        isolated.mkdir()
        (isolated / "python3").symlink_to(shutil.which("python3"))
        env = {**self.env, "PATH": str(isolated)}
        missing = self.run_listing("ls-by-name", env=env)
        self.assertEqual(missing.returncode, 127)
        self.assertIn("eza is required", missing.stderr)
        (isolated / "eza").symlink_to(shutil.which("eza"))
        many = self.root / "no-less"
        many.mkdir()
        for n in range(30):
            (many / f"entry-{n}").touch()
        self.terminal_listing([str(self.bin / "ls-by-name"), *PLAIN, str(many)], False, env=env)

    def test_shell_pipes_and_no_automatic_color(self):
        for shell in ("bash", "zsh", "nu"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                expression = "ls-by-name | cat" if shell != "nu" else "ls-by-name | lines | length"
                prefix = {"bash": ["--noprofile", "--norc"], "zsh": ["-f"], "nu": ["--no-config-file"]}[shell]
                result = subprocess.run([shell, *prefix, "-c", expression], cwd=self.data,
                                        env=self.env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("\x1b", result.stdout)
                if shell == "nu":
                    self.assertEqual(result.stdout.strip(), "3")
                else:
                    self.assertIn("a.txt", result.stdout)

    def terminal_listing(self, args, expect_pager, env=None, stdin_pipe=False, stdout_pipe=False, expected_status=0):
        pid, master = pty.fork()
        if pid == 0:
            fcntl.ioctl(1, termios.TIOCSWINSZ, struct.pack("HHHH", 12, 60, 0, 0))
            if stdin_pipe:
                read, write = os.pipe()
                os.close(write)
                os.dup2(read, 0)
                os.close(read)
            if stdout_pipe:
                # A shell pipe whose final output still reaches the terminal.
                os.execvpe("bash", ["bash", "--norc", "-c", '"$@" | cat', "bash", *args], env or self.env)
            os.execvpe(args[0], args, env or self.env)
        output = bytearray()
        status = None
        quit_sent = False
        deadline = time.monotonic() + 5
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.05)
                if ready:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        chunk = b""
                    output.extend(chunk)
                # less uses ':' mid-file and inverse video at EOF.
                pager_visible = b":\x1b[K" in output or b"\x1b[7m" in output
                if expect_pager and pager_visible and not quit_sent:
                    os.write(master, b"q")
                    quit_sent = True
                ended, status_value = os.waitpid(pid, os.WNOHANG)
                if ended:
                    status = os.waitstatus_to_exitcode(status_value)
                    break
            self.assertIsNotNone(status, f"command hung: {bytes(output)!r}")
            self.assertEqual(status, expected_status, bytes(output))
            self.assertEqual(quit_sent, expect_pager, bytes(output))
            if not expect_pager:
                self.assertNotIn(b"\x1b[7m", output)
                self.assertNotIn(b":\x1b[K", output)
            return bytes(output)
        finally:
            if status is None:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(master)

    def test_real_pager_short_long_wrapped_and_bypasses(self):
        many = self.root / "many"
        many.mkdir()
        for n in range(100):
            (many / f"file-{n:03}").touch()
        command = str(self.bin / "ls-by-name")
        self.terminal_listing([command, *PLAIN, str(self.data)], False)
        self.terminal_listing([command, *PLAIN, str(many)], True)
        self.terminal_listing([command, *PLAIN, "--no-pager", str(many)], False)
        self.terminal_listing([command, *PLAIN, str(many)], False, stdin_pipe=True)
        self.terminal_listing([command, *PLAIN, str(many)], False, stdout_pipe=True)
        self.terminal_listing([command, *PLAIN, str(many)], False, env={**self.env, "TERM": "dumb"})
        self.terminal_listing([command, *PLAIN, str(many)], False, env={**self.env, "TERM": ""})
        wide = self.root / "wide"
        wide.mkdir()
        for n in range(4):
            (wide / (str(n) + "x" * 220)).touch()
        self.terminal_listing([command, *PLAIN, str(wide)], True,
                              env={**self.env, "LESS": "-S -+F"})

    def test_paged_error_status_is_preserved(self):
        path = str(self.root / "absent")
        expected = subprocess.run(["eza", path], capture_output=True).returncode
        self.terminal_listing([str(self.bin / "ls-by-name"), path], False, expected_status=expected)


if __name__ == "__main__":
    unittest.main()
