"""Exercise bookmarks through the public CLI and real Bash, Zsh, and Nu adapters."""

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
SOURCE = SCRIPTS / "bin/executable_dir-bookmark"


class DirectoryBookmarkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.command = self.bin / "dir-bookmark"
        shutil.copyfile(SOURCE, self.command)
        self.command.chmod(0o755)
        self.env = {**os.environ, "HOME": str(self.home), "PWD": str(self.root),
                    "XDG_DATA_HOME": str(self.root / "data"),
                    "XDG_STATE_HOME": str(self.root / "state"),
                    "PATH": f"{self.bin}:{os.environ['PATH']}", "FZF_DEFAULT_OPTS": "",
                    "PRODUCTIVITY_SOURCE": str(SCRIPTS / "shell/productivity.sh")}
        self.env.pop("FZF_DEFAULT_OPTS_FILE", None)
        self.storage = self.root / "data/dir-bookmark/bookmarks.json"
        self.legacy = self.home / ".bookmarks.nuon"
        config = self.home / ".config/nushell"
        config.mkdir(parents=True)
        for name in ("alias.nu", "bookmark.nu"):
            shutil.copyfile(REPO / "private_dot_config/nushell" / name, config / name)

    def run_cli(self, *args, env=None, cwd=None):
        return subprocess.run([sys.executable, str(self.command), *map(str, args)],
                              env=env or self.env, cwd=cwd or self.root,
                              capture_output=True, timeout=15)

    def ok(self, *args, **kwargs):
        result = self.run_cli(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result

    def rows(self):
        return json.loads(self.ok("list", "--json").stdout)

    def directory(self, name):
        path = self.root / name
        path.mkdir(parents=True)
        return path

    def test_xdg_location_absolute_override_and_relative_fallback(self):
        self.assertEqual(self.ok("path").stdout.decode().strip(), str(self.storage))
        self.assertFalse(self.storage.exists())
        fallback = self.home / ".local/share/dir-bookmark/bookmarks.json"
        for value in ("", "relative"):
            env = {**self.env, "XDG_DATA_HOME": value}
            self.assertEqual(self.ok("path", env=env).stdout.decode().strip(), str(fallback))

    def test_add_defaults_relative_paths_symlinks_and_exact_output(self):
        target = self.directory(" 한글 space\ttab\nnewline\n")
        self.ok("add", "unusual", target)
        self.assertEqual(self.ok("pick", "unusual", "--null").stdout, os.fsencode(target) + b"\0")
        self.assertEqual(json.loads(self.ok("pick", "unusual", "--json").stdout), str(target))
        self.ok("add", "relative", target.name)
        self.assertEqual(self.rows()[1]["path"], str(target))
        link = self.root / "logical link"
        link.symlink_to(target, target_is_directory=True)
        self.ok("add", env={**self.env, "PWD": str(link)}, cwd=link)
        self.assertEqual(self.rows()[-1], {"name": "logical link", "path": str(link)})
        self.assertEqual(self.storage.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.storage.parent.stat().st_mode & 0o777, 0o700)

    def test_stale_exported_pwd_falls_back_to_actual_directory(self):
        self.ok("add", "here", env={**self.env, "PWD": "/does/not/exist"})
        self.assertEqual(self.rows(), [{"name": "here", "path": str(self.root)}])

    def test_conflicts_require_replace_and_invalid_add_preserves_store(self):
        first, second = self.directory("first"), self.directory("second")
        self.ok("add", "work", first)
        original = self.storage.read_bytes()
        self.ok("add", "work", first)
        self.assertEqual(self.storage.read_bytes(), original)
        for arguments in (("add", "work", second), ("add", "missing", self.root / "absent")):
            result = self.run_cli(*arguments)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.storage.read_bytes(), original)
        self.ok("add", "work", second, "--replace")
        self.assertEqual(self.rows(), [{"name": "work", "path": str(second)}])

    def test_delete_only_removes_bookmarks_and_unknown_names_are_atomic(self):
        target = self.directory("keep directory")
        self.ok("add", "saved", target)
        result = self.run_cli("delete", "saved", "unknown")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(self.rows()), 1)
        self.ok("delete", "saved")
        self.assertEqual(self.rows(), [])
        self.assertTrue(target.is_dir())

    def test_missing_targets_are_reported_and_bookmarks_kept(self):
        target = self.directory("later missing")
        self.ok("add", "saved", target)
        target.rmdir()
        result = self.run_cli("pick", "saved", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"bookmark kept", result.stderr)
        self.assertEqual(len(self.rows()), 1)

    def test_bad_storage_is_reported_without_overwriting(self):
        self.storage.parent.mkdir(parents=True)
        for contents in ('{"broken":', '{"version":99,"bookmarks":[]}',
                         '{"version":1,"bookmarks":[{"name":"bad","path":"relative"}]}'):
            with self.subTest(contents=contents):
                self.storage.write_text(contents)
                result = self.run_cli("list", "--json")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(self.storage.read_text(), contents)

    @unittest.skipUnless(shutil.which("nu"), "requires Nu for legacy conversion")
    def test_legacy_import_preserves_original_records_and_happens_once(self):
        first, second = self.directory("legacy first"), self.directory("legacy second")
        # The table syntax is the format written by the old Nushell manager.
        self.legacy.write_text(f'[[name, path]; ["same", {json.dumps(str(first))}], '
                               f'["same", {json.dumps(str(second))}]]')
        original = self.legacy.read_bytes()
        self.ok("migrate")
        self.assertEqual(self.rows(), [{"name": "same", "path": str(first)},
                                       {"name": "same-2", "path": str(second)}])
        self.assertEqual(self.legacy.read_bytes(), original)
        self.assertEqual(json.loads(self.ok("list", "--json", env={**self.env, "PATH": str(self.bin)}).stdout),
                         self.rows())
        self.ok("delete", "same", "same-2")
        self.ok("migrate")
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.legacy.read_bytes(), original)

    @unittest.skipUnless(shutil.which("nu"), "requires Nu for legacy conversion")
    def test_bad_legacy_prevents_initialization_without_losing_original(self):
        self.legacy.write_text('[[name, path]; ["unfinished"')
        result = self.run_cli("migrate")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"cannot import", result.stderr)
        self.assertFalse(self.storage.exists())
        self.assertEqual(self.legacy.read_text(), '[[name, path]; ["unfinished"')

    def test_regular_operations_do_not_require_nushell(self):
        env = {**self.env, "PATH": str(self.bin)}
        self.ok("add", "here", self.root, env=env)
        self.assertEqual(json.loads(self.ok("list", "--json", env=env).stdout)[0]["name"], "here")
        self.ok("delete", "here", env=env)

    def test_interactive_delete_preserves_a_concurrently_reassigned_name(self):
        first, second = self.directory("old binding"), self.directory("new binding")
        self.ok("add", "shared", first)
        fzf = self.bin / "fzf"
        fzf.write_text(f'#!{sys.executable}\n'
                       'import os, subprocess, sys\n'
                       'sys.stdin.buffer.read()\n'
                       'subprocess.run([sys.executable, os.environ["BOOKMARK_CLI"], "add", '
                       '"shared", os.environ["NEW_BINDING"], "--replace"], check=True)\n'
                       'sys.stdout.buffer.write(b"0\\0")\n')
        fzf.chmod(0o755)
        env = {**self.env, "BOOKMARK_CLI": str(self.command), "NEW_BINDING": str(second)}
        self.ok("delete", env=env)
        self.assertEqual(self.rows(), [{"name": "shared", "path": str(second)}])

    def test_picker_cancellation_and_invalid_output_never_mutate_bookmarks(self):
        self.ok("add", "known", self.root)
        original = self.storage.read_bytes()
        fzf = self.bin / "fzf"
        for output, status, expected in (("", 130, 0), ("", 2, 2), ("bad\\0", 0, 2)):
            fzf.write_text(f'#!/bin/sh\nprintf "{output}"\nexit {status}\n')
            fzf.chmod(0o755)
            result = self.run_cli("pick", "--json")
            self.assertEqual(result.returncode, expected, result.stderr.decode())
            self.assertEqual(result.stdout, b"null\n" if expected == 0 else b"")
            self.assertEqual(self.storage.read_bytes(), original)

    def test_concurrent_writers_keep_every_bookmark(self):
        processes = []
        try:
            for number in range(16):
                target = self.directory(f"concurrent-{number}")
                processes.append(subprocess.Popen(
                    [sys.executable, str(self.command), "add", f"name-{number}", str(target)],
                    env=self.env, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            for process in processes:
                output, error = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, (output, error))
            self.assertEqual({row["name"] for row in self.rows()},
                             {f"name-{number}" for number in range(16)})
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_fzf_preserves_paths_and_cancellation_and_multi_delete(self):
        target = self.directory(" odd\tpath\nwith newline\n")
        self.ok("add", "needle\tname\n", target)
        self.ok("add", "other", self.root)
        env = {**self.env, "FZF_DEFAULT_OPTS": "--filter=needle"}
        self.assertEqual(self.ok("pick", "--null", env=env).stdout, os.fsencode(target) + b"\0")
        original = self.storage.read_bytes()
        env = {**self.env, "FZF_DEFAULT_OPTS": "--filter=unmatched"}
        self.assertEqual(self.ok("pick", "--json", env=env).stdout, b"null\n")
        self.ok("delete", env=env)
        self.assertEqual(self.storage.read_bytes(), original)
        env = {**self.env, "FZF_DEFAULT_OPTS": "--filter="}
        self.ok("delete", env=env)
        self.assertEqual(self.rows(), [])
        self.assertTrue(target.is_dir())

    def run_shell(self, shell, code, env=None):
        if shell == "nu":
            setup = 'def ezam [...args] {}; source ~/.config/nushell/alias.nu; '
            command = [shell, "--no-config-file", "--no-history", "-c", setup + code]
        else:
            options = ["--noprofile", "--norc"] if shell == "bash" else ["-f"]
            setup = 'shopt -s expand_aliases; ' if shell == "bash" else ''
            setup += 'alias cd=cl; source "$PRODUCTIVITY_SOURCE"; l() { :; }; '
            if shell == "zsh":
                setup += 'chpwd_functions=(); '
            command = [shell, *options, "-c", setup + 'eval "$BOOKMARK_TEST"']
        return subprocess.run(command, cwd=self.root,
                              env={**(env or self.env), "BOOKMARK_TEST": code},
                              capture_output=True, timeout=15)

    def test_all_shell_adapters_share_add_jump_list_and_delete(self):
        target = self.directory(" shell path\twith\ntrailing space \n")
        env = {**self.env, "BOOKMARK_TARGET": str(target)}
        for shell in ("bash", "zsh", "nu"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                add = 'ba shared $env.BOOKMARK_TARGET' if shell == "nu" else 'ba shared "$BOOKMARK_TARGET"'
                result = self.run_shell(shell, add, env)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(self.rows(), [{"name": "shared", "path": str(target)}])
                code = 'bm shared; $env.PWD | to json --raw' if shell == "nu" else (
                    'bm shared || exit; python3 -c \'import json,os; print(json.dumps(os.getcwd()))\'')
                result = self.run_shell(shell, code, env)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(json.loads(result.stdout.splitlines()[-1]), str(target))
                listing = 'bl | to json --raw' if shell == "nu" else 'bl --json'
                result = self.run_shell(shell, listing, env)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(json.loads(result.stdout), self.rows())
                result = self.run_shell(shell, 'bd shared', env)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(self.rows(), [])

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_all_shell_pickers_and_cancellation_preserve_cwd(self):
        target = self.directory("picker target")
        self.ok("add", "needle", target)
        for shell in ("bash", "zsh", "nu"):
            if not shutil.which(shell):
                continue
            for query, expected in (("needle", target), ("absent", self.root)):
                with self.subTest(shell=shell, query=query):
                    env = {**self.env, "FZF_DEFAULT_OPTS": f"--filter={query}"}
                    code = 'bm; $env.PWD | to json --raw' if shell == "nu" else (
                        'bm || exit; python3 -c \'import json,os; print(json.dumps(os.getcwd()))\'')
                    result = self.run_shell(shell, code, env)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(json.loads(result.stdout.splitlines()[-1]), str(expected))

    def test_directory_aliases_all_shells_and_runtime_tmpdir(self):
        for relative in (".local/share/chezmoi", "gh", "works"):
            (self.home / relative).mkdir(parents=True)
        first, second = self.directory("temp first"), self.directory("temp second")
        env = {**self.env, "TMPDIR": str(first), "NEXT_TMPDIR": str(second)}
        aliases = {"dir-chez": self.home / ".local/share/chezmoi",
                   "dir-gh": self.home / "gh", "dir-works": self.home / "works",
                   "dir-tmp": first, "tmpd": first}
        for shell in ("bash", "zsh", "nu"):
            if not shutil.which(shell):
                continue
            for alias, expected in aliases.items():
                with self.subTest(shell=shell, alias=alias):
                    code = f'{alias}; $env.PWD | to json --raw' if shell == "nu" else (
                        f'{alias} || exit; python3 -c \'import json,os; print(json.dumps(os.getcwd()))\'')
                    result = self.run_shell(shell, code, env)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(json.loads(result.stdout.splitlines()[-1]), str(expected))
            code = ('$env.TMPDIR = $env.NEXT_TMPDIR; dir-tmp; $env.PWD | to json --raw' if shell == "nu" else
                    'TMPDIR=$NEXT_TMPDIR; dir-tmp || exit; python3 -c \'import json,os; print(json.dumps(os.getcwd()))\'')
            result = self.run_shell(shell, code, env)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(json.loads(result.stdout.splitlines()[-1]), str(second))

    def test_shell_navigation_errors_and_interrupt_leave_directory_unchanged(self):
        for shell in ("bash", "zsh", "nu"):
            if not shutil.which(shell):
                continue
            with self.subTest(shell=shell):
                result = self.run_shell(shell, 'bm nonexistent')
                self.assertNotEqual(result.returncode, 0)
                fake = self.bin / "dir-bookmark"
                original = fake.read_bytes()
                try:
                    fake.write_text('#!/bin/sh\nexit 130\n')
                    code = ('bm; $env.PWD | to json --raw' if shell == "nu" else
                            'bm || exit; python3 -c \'import json,os; print(json.dumps(os.getcwd()))\'')
                    result = self.run_shell(shell, code)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(json.loads(result.stdout), str(self.root))
                finally:
                    fake.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
