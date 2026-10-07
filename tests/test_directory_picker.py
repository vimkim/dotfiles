"""Public CLI, real fzf terminal, and shell navigation checks."""

import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "private_dot_config/my-scripts/bin/executable_dir-picker"



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

    def test_recency_uses_modification_time_independent_of_creation(self):
        older = self.data / "older"
        older.mkdir()
        time.sleep(0.02)
        newer = self.data / "newer"
        newer.mkdir()
        os.utime(older, ns=(2_000_000_000_000_000_000,) * 2)
        os.utime(newer, ns=(1_000_000_000_000_000_000,) * 2)
        result = self.run_picker("--list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [str(self.root), str(older), str(newer)])

    def test_symlink_target_recency_ties_and_directory_inclusion(self):
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
        result = self.run_picker("--list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = [self.root, *[self.data / name for name in [".hidden", "a", "b", "link"]]]
        self.assertEqual(json.loads(result.stdout), [str(path) for path in expected])

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

    def terminal_selection(self, keys, *args, env=None):
        """Drive the public picker UI with keystrokes and capture its output."""
        output = self.root / "selection.json"
        pid, terminal = pty.fork()
        if pid == 0:
            os.chdir(self.data)
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.dup2(descriptor, 1)
            os.close(descriptor)
            terminal_env = {**(env or self.env), "TERM": "xterm-256color"}
            os.execve(sys.executable, [sys.executable, str(self.command), "--json", *args], terminal_env)
        fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 120, 0, 0))
        rendered = b""
        next_key = 0
        send_after = None
        accepted = False
        exited = False
        terminal_open = True
        deadline = time.monotonic() + 8
        try:
            while time.monotonic() < deadline:
                if terminal_open and select.select([terminal], [], [], 0.05)[0]:
                    try:
                        chunk = os.read(terminal, 65536)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        chunk = b""
                    if not chunk:
                        terminal_open = False
                    rendered += chunk
                    if b"\x1b[6n" in chunk:
                        os.write(terminal, b"\x1b[1;1R")
                elif not terminal_open:
                    time.sleep(0.01)
                if send_after is None and b"Modified" in rendered:
                    send_after = time.monotonic() + 0.2
                if send_after is not None and time.monotonic() >= send_after and not accepted:
                    if next_key < len(keys):
                        os.write(terminal, keys[next_key])
                        next_key += 1
                        send_after = time.monotonic() + 0.2
                    else:
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
        return json.loads(output.read_text()), rendered

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_terminal_query_switches_recency_to_score_and_back(self):
        for name, timestamp in [("xabc", 3_000_000_000), ("abc", 2_000_000_000),
                                ("a_x_b_x_c", 1_000_000_000)]:
            directory = self.data / name
            directory.mkdir()
            os.utime(directory, ns=(timestamp,) * 2)
        env = {**self.env, "FZF_DEFAULT_OPTS": "--tac --no-sort"}
        for state, keys, expected in [
            ("empty", [b"\x0e"], "xabc"),
            ("single character", [b"a"], "abc"),
            ("fuzzy query", [b"abc"], "abc"),
            ("Ctrl-S", [b"abc", b"\x13"], "abc"),
            ("cleared", [b"abc", b"\x15", b"\x0e"], "xabc"),
        ]:
            with self.subTest(state=state):
                selected, _ = self.terminal_selection(keys, env=env)
                self.assertEqual(selected, str(self.data / expected))

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_metadata_is_visible_but_only_names_are_searchable(self):
        target = self.root / "secret-target"
        target.mkdir()
        os.utime(target, (946684800, 946684800))
        (self.data / "shortcut").symlink_to(target, target_is_directory=True)
        selected, rendered = self.terminal_selection([], env={**self.env, "TZ": "UTC"})
        self.assertEqual(selected, str(self.root))
        for visible in [b"Size", b"Modified", b"2000-01-01", b"secret-target",
                        "\uf07b".encode("utf-8")]:
            self.assertIn(visible, rendered)
        for query in ["2000", "secret-target", self.root.name, "\uf07b"]:
            with self.subTest(query=query):
                result = self.run_picker(env={**self.env, "FZF_DEFAULT_OPTS": "--filter=" + query})
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, b"")

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_initial_query_selects_by_score_and_accepts_empty_text(self):
        for name, timestamp in [("xabc", 2_000_000_000), ("abc", 1_000_000_000)]:
            directory = self.data / name
            directory.mkdir()
            os.utime(directory, ns=(timestamp,) * 2)
        for query, expected in [("abc", self.data / "abc"), ("", self.root)]:
            with self.subTest(query=query):
                selected, _ = self.terminal_selection([], "--query", query, str(self.data))
                self.assertEqual(selected, str(expected))

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_name_matching_keeps_fuzzy_extended_smartcase_semantics(self):
        target = self.data / "A_x_B_x_C"
        target.mkdir()
        defaults = "--exact --no-extended --no-ignore-case --scheme=history"
        for query, expected in [("abc", str(target)), ("^A C$ !old", str(target)), ("Abc", None)]:
            with self.subTest(query=query):
                env = {**self.env, "FZF_DEFAULT_OPTS": defaults + " --filter=" + shlex.quote(query)}
                result = self.run_picker("--json", env=env)
                if expected is None:
                    self.assertEqual(result.returncode, 1, result.stderr)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), expected)

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_escaped_names_keep_distinct_original_paths(self):
        cases = [
            ("line\nname", r"^line\nname$"),
            (r"line\nname", r"^line\\nname$"),
            ("tab\tname", r"^tab\tname$"),
            ("control\x1bname", r"^control\u001bname$"),
        ]
        for name, _ in cases:
            (self.data / name).mkdir()
        for name, query in cases:
            with self.subTest(name=name):
                env = {**self.env, "FZF_DEFAULT_OPTS": "--filter=" + shlex.quote(query)}
                result = self.run_picker("--null", env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, os.fsencode(self.data / name) + b"\0")

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_tied_scores_and_empty_patterns_keep_recency(self):
        for name, timestamp in [("antelope", 2_000_000_000), ("alpha", 1_000_000_000)]:
            directory = self.data / name
            directory.mkdir()
            os.utime(directory, ns=(timestamp,) * 2)
        for keys in [[b"a"], [b"   ", b"\x0e"], [b"!absent", b"\x0e"]]:
            with self.subTest(keys=keys):
                selected, _ = self.terminal_selection(keys)
                self.assertEqual(selected, str(self.data / "antelope"))

    def cancel_fzf(self, status):
        """Exercise cancellation at the external terminal-program boundary."""
        command = self.bin / "fzf"
        command.write_text(
            f"#!{sys.executable}\nimport sys\nsys.exit({status})\n"
        )
        command.chmod(0o755)

    def run_nushell(self, expression):
        code = (
            "def ezam [] {}; "
            f"source {json.dumps(str(REPO / 'private_dot_config/nushell/alias.nu'))}; "
            f"{expression}; $env.PWD | to json --raw"
        )
        return subprocess.run(["nu", "--no-config-file", "-c", code], cwd=self.data,
                              env=self.env, capture_output=True, text=True, timeout=10)

    def run_shell(self, shell, direct=False):
        if shell == "nu":
            return self.run_nushell("c $env.DIRECT_PATH" if direct else "c")
        code = (
            '_cached_source() { :; }; '
            'source "$ALIASES_SOURCE"; my-list-long() { :; }; '
            f"eval 'c{' \"$DIRECT_PATH\"' if direct else ''}'; "
            'python3 -c \'import json, os; print(json.dumps(os.getcwd()))\''
        )
        return subprocess.run(["zsh", "-f", "-c", code], cwd=self.data, env=self.env,
                              capture_output=True, text=True, timeout=10)

    @unittest.skipUnless(shutil.which("nu") and shutil.which("fzf"), "requires nu and fzf")
    def test_nushell_query_browses_current_or_supplied_root(self):
        target = self.data / "needle"
        target.mkdir()
        dash = self.data / "-needle"
        dash.mkdir()
        root = self.data / "-other root"
        root.mkdir()
        nested = root / "needle"
        nested.mkdir()
        self.env["BROWSE_ROOT"] = "-other root"
        empty = self.data / "empty root"
        empty.mkdir()
        self.env["EMPTY_ROOT"] = str(empty)
        self.env["FZF_DEFAULT_OPTS"] = "--select-1 --exit-0"
        for expression, expected in [
            ('c --query "^needle$"', target),
            ('c $env.BROWSE_ROOT --query "^needle$"', nested),
            ('c --query "-needle"', dash),
            ('c $env.EMPTY_ROOT --query ""', self.data),
        ]:
            with self.subTest(expression=expression):
                result = self.run_nushell(expression)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), str(expected))
        for status in [1, 130]:
            with self.subTest(cancelled=status):
                self.cancel_fzf(status)
                result = self.run_nushell('c $env.BROWSE_ROOT --query "^needle$"')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), str(self.data))

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_shell_selection_direct_navigation_parent_and_cancellation(self):
        target = self.data / " 한글 space\ttab\nnewline\n"
        target.mkdir()
        self.env["ALIASES_SOURCE"] = str(REPO / "private_dot_config/my-scripts/zsh/aliases.zsh")
        self.env["DIRECT_PATH"] = str(target)
        for shell in ["nu", "zsh"]:
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                (self.bin / "fzf").unlink(missing_ok=True)
                self.env["FZF_DEFAULT_OPTS"] = "--filter=한글"
                selected = self.run_shell(shell)
                self.assertEqual(selected.returncode, 0, selected.stderr)
                self.assertEqual(json.loads(selected.stdout), str(target))
                direct = self.run_shell(shell, direct=True)
                self.assertEqual(direct.returncode, 0, direct.stderr)
                self.assertEqual(json.loads(direct.stdout), str(target))
                self.env["FZF_DEFAULT_OPTS"] = "--filter=^../$"
                parent = self.run_shell(shell)
                self.assertEqual(parent.returncode, 0, parent.stderr)
                self.assertEqual(json.loads(parent.stdout), str(self.root))
                for status in [1, 130]:
                    self.cancel_fzf(status)
                    cancelled = self.run_shell(shell)
                    self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
                    self.assertEqual(json.loads(cancelled.stdout), str(self.data))


if __name__ == "__main__":
    unittest.main()
