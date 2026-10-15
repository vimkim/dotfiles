"""Exercise the shared shortcuts in real Bash and Zsh processes."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "private_dot_config/my-scripts"
SOURCE = SCRIPTS / "shell/productivity.sh"


class ShellProductivityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("dir-picker", "file-picker.sh"):
            target = self.bin / name
            shutil.copyfile(SCRIPTS / "bin" / ("executable_" + name), target)
            target.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}",
                    "PRODUCTIVITY_SOURCE": str(SOURCE), "TMPDIR": str(self.root),
                    "FZF_DEFAULT_OPTS": "", "FALLBACK_BIN": str(self.bin)}
        self.env.pop("FZF_DEFAULT_OPTS_FILE", None)

    def shells(self):
        return [shell for shell in ("bash", "zsh") if shutil.which(shell)]

    def run_shell(self, shell, code, listing=False):
        prefix = ["--noprofile", "--norc"] if shell == "bash" else ["-f"]
        setup = 'alias c=false l=false cf=false vc=false y=false; source "$PRODUCTIVITY_SOURCE"; '
        if shell == "bash":
            setup = 'shopt -s expand_aliases; ' + setup
        if not listing:
            setup += 'l() { :; }; '
        return subprocess.run([shell, *prefix, "-c", setup + 'eval "$TEST_CODE"'],
                              cwd=self.data, env={**self.env, "TEST_CODE": code},
                              capture_output=True, text=True, timeout=10)

    def assert_cwd(self, shell, expression, expected):
        result = self.run_shell(shell, expression + "; " +
                                "python3 -c 'import json, os; print(json.dumps(os.getcwd()))'")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), str(expected))

    def test_picker_direct_paths_queries_cancellation_and_errors(self):
        target = self.data / " 한글 space\ttab\nnewline\n"
        target.mkdir()
        self.env["TARGET"] = str(target)
        for shell in self.shells():
            with self.subTest(shell=shell):
                self.env["FZF_DEFAULT_OPTS"] = "--filter=한글"
                self.assert_cwd(shell, 'c', target)
                self.assert_cwd(shell, 'c "$TARGET"', target)
                self.env["FZF_DEFAULT_OPTS"] = "--select-1 --exit-0"
                self.assert_cwd(shell, 'c --query 한글', target)
                self.env["FZF_DEFAULT_OPTS"] = "--filter=absent"
                self.assert_cwd(shell, 'c', self.data)
                error = self.run_shell(shell, 'c --query')
                self.assertEqual(error.returncode, 2, error.stderr)
                error = self.run_shell(shell, 'c absent --query x')
                self.assertEqual(error.returncode, 2, error.stderr)
                # Verify cancellation and genuine picker failures stay distinct.
                for status in (130, 127):
                    picker = self.bin / "dir-picker"
                    original = picker.read_bytes()
                    try:
                        picker.write_text(f"#!/bin/sh\nexit {status}\n")
                        result = self.run_shell(shell, 'c')
                        self.assertEqual(result.returncode, 0 if status == 130 else status)
                    finally:
                        picker.write_bytes(original)

    def test_navigation_git_root_and_mkdir_with_spaces(self):
        repository = self.data / "repository with spaces"
        repository.mkdir()
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        child = repository / "child"
        child.mkdir()
        self.env["CHILD"] = str(child)
        for shell in self.shells():
            with self.subTest(shell=shell):
                self.assert_cwd(shell, 'c "$CHILD"; gr', repository)
                self.assert_cwd(shell, 'c "$CHILD"; gcd', repository)
                self.assert_cwd(shell, 'c "$CHILD"; h', repository)
                destination = self.data / f"{shell} parent" / "new directory"
                self.env["DESTINATION"] = str(destination)
                self.assert_cwd(shell, 'mc "$DESTINATION"', destination)
                self.assertEqual(self.run_shell(shell, 'mc').returncode, 2)

    @unittest.skipUnless(shutil.which("eza"), "requires eza")
    def test_listings_include_hidden_and_all_entries_without_pipe_color(self):
        (self.data / ".hidden").touch()
        for number in range(405):
            (self.data / f"file-{number:03}").touch()
        self.env["TARGET"] = str(self.data)
        for shell in self.shells():
            for command in ('l', 'll "$TARGET"', 'sl'):
                with self.subTest(shell=shell, command=command):
                    result = self.run_shell(shell, command, listing=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(".hidden", result.stdout)
                    self.assertIn("file-404", result.stdout)
                    self.assertNotIn("\x1b", result.stdout)

    def test_listings_fall_back_to_system_ls(self):
        (self.data / ".hidden").touch()
        (self.data / "visible").touch()
        (self.bin / "ls").symlink_to(shutil.which("ls"))
        for shell in self.shells():
            with self.subTest(shell=shell):
                result = self.run_shell(shell, 'PATH="$FALLBACK_BIN"; l; ll', listing=True)
                # The shell itself is resolved before the restricted PATH is set.
                # FALLBACK_BIN contains ls, but has no eza.
                if result.returncode:
                    self.fail(result.stderr)
                self.assertIn(".hidden", result.stdout)
                self.assertIn("visible", result.stdout)

    @unittest.skipUnless(all(shutil.which(tool) for tool in ("fd", "eza", "fzf")),
                         "requires fd, eza, and fzf")
    def test_file_picker_navigation_editing_and_cancellation(self):
        directory = self.data / "project with spaces"
        directory.mkdir()
        target = directory / "chosen file.txt"
        target.touch()
        self.env["TARGET_DIR"] = str(directory)
        self.env["FZF_DEFAULT_OPTS"] = "--filter=chosen"
        editor = self.bin / "editor"
        editor.write_text(f'#!{sys.executable}\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
        editor.chmod(0o755)
        self.env["EDITOR"] = str(editor)
        for shell in self.shells():
            with self.subTest(shell=shell):
                result = self.run_shell(shell, 'fp')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(Path(result.stdout.strip()), target)
                self.assert_cwd(shell, 'cf', directory)
                result = self.run_shell(shell, 'c "$TARGET_DIR"; vc')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([Path(path) for path in json.loads(result.stdout)], [target])
                self.env["FZF_DEFAULT_OPTS"] = "--filter=absent"
                self.assert_cwd(shell, 'cf', self.data)
                self.env["FZF_DEFAULT_OPTS"] = "--filter=chosen"

    def test_yazi_enters_exit_directory_and_cleans_temporary_file(self):
        target = self.data / "yazi directory"
        target.mkdir()
        self.env["TARGET"] = str(target)
        yazi = self.bin / "yazi"
        yazi.write_text('#!/bin/sh\nfor arg do\ncase "$arg" in\n'
                        '--cwd-file=*) printf "%s\\n" "$TARGET" > "${arg#*=}";;\nesac\ndone\n')
        yazi.chmod(0o755)
        for shell in self.shells():
            with self.subTest(shell=shell):
                self.assert_cwd(shell, 'y', target)
                self.assertEqual(list(self.root.glob("yazi-cwd.*")), [])


if __name__ == "__main__":
    unittest.main()
