"""Exercise the shared shortcuts in real Bash and Zsh processes."""

import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
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
        for name in ("dir-picker", "file-picker.sh", "directory-history.nu"):
            target = self.bin / name
            shutil.copyfile(SCRIPTS / "bin" / ("executable_" + name), target)
            target.chmod(0o755)
        self.home = self.root / "home"
        nu_config = self.home / ".config/nushell"
        nu_config.mkdir(parents=True)
        shutil.copyfile(REPO / "private_dot_config/nushell/dir-history.nu",
                        nu_config / "dir-history.nu")
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}",
                    "PRODUCTIVITY_SOURCE": str(SOURCE), "TMPDIR": str(self.root),
                    "FZF_DEFAULT_OPTS": "", "FALLBACK_BIN": str(self.bin),
                    "HOME": str(self.home)}
        self.env.pop("FZF_DEFAULT_OPTS_FILE", None)

    def shells(self):
        return [shell for shell in ("bash", "zsh") if shutil.which(shell)]

    def run_shell(self, shell, code, listing=False):
        prefix = ["--noprofile", "--norc"] if shell == "bash" else ["-f"]
        setup = ('alias c=false l=false cf=false vc=false y=false '
                 'ch=false n=false nr=false na=false nc=false; source "$PRODUCTIVITY_SOURCE"; ')
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
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]), str(expected))

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

    @unittest.skipUnless(all(shutil.which(tool) for tool in ("nu", "fzf")),
                         "requires nu and fzf")
    def test_directory_history_record_pick_cancel_forget_and_prune(self):
        target = self.data / "history directory"
        target.mkdir()
        self.env["TARGET"] = str(target)
        history = self.home / ".local/share/nu/dirlog.json"
        for shell in self.shells():
            with self.subTest(shell=shell):
                self.env["FZF_DEFAULT_OPTS"] = "--filter=history"
                code = ('builtin cd "$TARGET"; _productivity_record_directory; '
                        'builtin cd "$OLDPWD"; _productivity_record_directory; ch')
                self.assert_cwd(shell, code, target)
                self.env["FZF_DEFAULT_OPTS"] = "--filter=absent"
                self.assert_cwd(shell, 'ch', self.data)
                self.env["FZF_DEFAULT_OPTS"] = "--filter=history"
                result = self.run_shell(shell, 'ch --forget')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(str(target), json.loads(history.read_text()))
                missing = self.data / "missing directory"
                history.write_text(json.dumps([str(target), str(missing)]))
                result = self.run_shell(shell, 'ch --prune')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(history.read_text()), [str(target)])

    def install_recipe_picker(self):
        picker = self.bin / "just-pick-and-print.nu"
        picker.write_text(f'#!{sys.executable}\nimport json,os,sys\n'
                          'from pathlib import Path\n'
                          'Path(os.environ["PICKER_LOG"]).write_text(json.dumps(sys.argv[1:]))\n'
                          'print(os.environ.get("RECIPE", "build"))\n'
                          'sys.exit(int(os.environ.get("PICKER_STATUS", "0")))\n')
        picker.chmod(0o755)
        just = self.bin / "just"
        just.write_text(f'#!{sys.executable}\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
        just.chmod(0o755)
        self.env["PICKER_LOG"] = str(self.root / "picker.json")

    def test_just_picker_paths_quoting_cancellation_and_errors(self):
        self.install_recipe_picker()
        self.env["MY_CUBRID"] = str(self.root / "CUBRID's $workspace")
        paths = {"n": "./justfile", "na": str(self.home / ".config/my-scripts/justfile"),
                 "nr": self.env["MY_CUBRID"] + "/remote-nu.just",
                 "nc": self.env["MY_CUBRID"] + "/cubrid-justfiles/justfile"}
        for shell in self.shells():
            for shortcut, path in paths.items():
                with self.subTest(shell=shell, shortcut=shortcut):
                    self.env["RECIPE"] = "build"
                    result = self.run_shell(shell,
                        '_productivity_edit_command() { eval "$1"; }; ' + shortcut)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    expected = ["build"] if shortcut == "n" else ["-f", path, "-d", ".", "build"]
                    self.assertEqual(json.loads(result.stdout), expected)
                    self.assertEqual(json.loads(Path(self.env["PICKER_LOG"]).read_text()),
                                     ["-f", path, "-d", "."])
            self.env["RECIPE"] = ""
            result = self.run_shell(shell, '_productivity_edit_command() { return 99; }; n')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.env["PICKER_STATUS"] = "7"
            result = self.run_shell(shell, 'n')
            self.assertEqual(result.returncode, 7, result.stderr)
            self.env.pop("PICKER_STATUS")

    @unittest.skipUnless(shutil.which("zsh"), "requires zsh")
    def test_zsh_recipe_preloads_next_command_without_execution(self):
        self.install_recipe_picker()
        result = self.run_shell("zsh", 'n; read -zr queued; print -r -- "$queued"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "just build\n")

    @unittest.skipUnless(shutil.which("bash"), "requires bash")
    def test_bash_recipe_is_editable_before_execution_and_saved_to_history(self):
        self.install_recipe_picker()
        rcfile = self.root / "bashrc"
        rcfile.write_text('PS1="READY> "; source "$PRODUCTIVITY_SOURCE"\n')
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        process = subprocess.Popen(["bash", "--noprofile", "--rcfile", str(rcfile), "-i"],
                                   stdin=slave, stdout=slave, stderr=slave, cwd=self.data,
                                   env={**self.env, "TERM": "xterm"}, start_new_session=True)
        os.close(slave)
        self.addCleanup(process.wait, timeout=5)
        self.addCleanup(process.kill)

        def until(marker):
            output = b""
            deadline = time.monotonic() + 5
            while marker not in output and time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    output += os.read(master, 65536)
            self.assertIn(marker, output, output.decode(errors="replace"))
            return output

        until(b"READY> ")
        os.write(master, b"n\n")
        output = until(b"Run: just build")
        self.assertNotIn(b'["build"]', output)
        os.write(master, b'\x01\x0bjust edited "two words"\n')
        output = until(b"READY> ")
        self.assertIn(b'["edited", "two words"]', output)
        os.write(master, b"history 3\n")
        output = until(b"READY> ")
        self.assertIn(b'just edited "two words"', output)
        os.write(master, b"false\n")
        until(b"READY> ")
        os.write(master, b'printf "STATUS=%s\\n" "$?"\n')
        output = until(b"READY> ")
        self.assertIn(b"STATUS=1", output)


if __name__ == "__main__":
    unittest.main()
