"""Exercise shared history through its public CLI and real shell adapters."""

import json
import os
from pathlib import Path
import select
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "private_dot_config/my-scripts/bin/executable_dir-history"


class DirectoryHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.command = self.bin / "dir-history"
        shutil.copyfile(SOURCE, self.command)
        self.command.chmod(0o755)
        self.env = {**os.environ, "HOME": str(self.home),
                    "XDG_STATE_HOME": str(self.root / "state"),
                    "PATH": f"{self.bin}:{os.environ['PATH']}", "FZF_DEFAULT_OPTS": ""}
        self.env.pop("FZF_DEFAULT_OPTS_FILE", None)
        self.database = self.root / "state/dir-history/history.sqlite3"
        self.legacy = self.home / ".local/share/nu/dirlog.json"

    def run_cli(self, *args, input=None, env=None):
        return subprocess.run([sys.executable, str(self.command), *map(str, args)],
                              env=env or self.env, cwd=self.root,
                              input=input, capture_output=True, timeout=10)

    def ok(self, *args, **kwargs):
        result = self.run_cli(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result

    def paths(self):
        return json.loads(self.ok("list", "--json").stdout)

    def directory(self, name):
        path = self.root / name
        path.mkdir()
        return str(path)

    def seed_legacy(self, paths):
        self.legacy.parent.mkdir(parents=True, exist_ok=True)
        self.legacy.write_text(json.dumps(paths))

    def test_migration_retains_order_original_and_once_only_semantics(self):
        paths = [self.directory(name) for name in ("newest", "older", "oldest")]
        self.seed_legacy([paths[0], paths[1], paths[0], None, "relative", paths[2]])
        original = self.legacy.read_bytes()
        self.ok("migrate")
        self.assertEqual(self.paths(), paths)
        self.assertEqual(self.legacy.read_bytes(), original)
        self.ok("forget", "--", paths[1])
        self.seed_legacy(paths)
        self.ok("migrate")
        self.assertEqual(self.paths(), [paths[0], paths[2]])
        self.ok("record", "--", paths[2])
        self.assertEqual(self.paths(), [paths[2], paths[0]])
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.database.stat().st_mode & 0o777, 0o600)

    def test_retention_is_part_of_recording(self):
        paths = [str(self.root / f"older-{number}") for number in range(151)]
        self.seed_legacy(paths)
        self.assertEqual(self.paths(), paths[:150])
        newest = self.directory("newest")
        self.ok("record", "--", newest)
        self.assertEqual(self.paths(), [newest, *paths[:149]])

    def test_bad_legacy_and_database_errors_preserve_data(self):
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_text('["incomplete')
        result = self.run_cli("migrate")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"cannot import", result.stderr)
        self.assertEqual(self.legacy.read_text(), '["incomplete')
        path = self.directory("recovered")
        self.seed_legacy([path])
        self.assertEqual(self.paths(), [path])
        self.database.write_bytes(b"damaged history database")
        result = self.run_cli("list", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(self.database.read_bytes(), b"damaged history database")

    def test_unknown_schema_is_not_reinitialized(self):
        self.database.parent.mkdir(parents=True)
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE unrelated(value TEXT)")
            db.execute("INSERT INTO unrelated VALUES ('preserve')")
            db.execute("PRAGMA user_version=99")
        result = self.run_cli("list", "--json")
        self.assertEqual(result.returncode, 2)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT value FROM unrelated").fetchone()[0], "preserve")
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_simultaneous_cold_start_writers_preserve_every_path(self):
        paths = [self.directory(f"concurrent-{number}") for number in range(24)]
        processes = []
        try:
            for path in paths:
                code = ('import runpy,sys; sys.stdin.readline(); '
                        'sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")')
                processes.append(subprocess.Popen(
                    [sys.executable, "-B", "-c", code, str(self.command), "record", "--", path],
                    env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            for process in processes:
                process.stdin.write(b"go\n")
                process.stdin.flush()
            for process in processes:
                output, error = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, (output, error))
            self.assertEqual(set(self.paths()), set(paths))
            self.assertEqual(len(self.paths()), len(paths))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)

    def test_busy_writer_reports_error_and_can_retry_without_reset(self):
        path = self.directory("known")
        self.ok("record", "--", path)
        newer = self.directory("newer")
        with sqlite3.connect(self.database) as db:
            db.execute("BEGIN IMMEDIATE")
            result = self.run_cli("record", "--", newer)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"locked", result.stderr)
            # WAL readers can still see committed history during the write lock.
            self.assertEqual(self.paths(), [path])
        self.ok("record", "--", newer)
        self.assertEqual(self.paths(), [newer, path])

    def test_stale_picker_cannot_remove_a_forgotten_then_revisited_path(self):
        path = self.directory("revisited")
        self.ok("record", "--", path)
        ready = self.root / "picker-ready"
        release = self.root / "release-picker"
        fzf = self.bin / "fzf"
        fzf.write_text(f'#!{sys.executable}\nimport os,pathlib,sys,time\n'
                       'sys.stdin.buffer.read()\n'
                       'pathlib.Path(os.environ["PICKER_READY"]).touch()\n'
                       'while not pathlib.Path(os.environ["PICKER_RELEASE"]).exists(): time.sleep(0.01)\n'
                       'sys.stdout.buffer.write(b"0\\0")\n')
        fzf.chmod(0o755)
        process = subprocess.Popen([sys.executable, str(self.command), "pick"],
            env={**self.env, "PICKER_READY": str(ready), "PICKER_RELEASE": str(release)},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(ready.exists())
            self.ok("forget", "--", path)
            self.ok("record", "--", path)
            Path(path).rmdir()
            release.touch()
            output, error = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, error)
            self.assertEqual(output, b"")
            self.assertEqual(self.paths(), [path])
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def test_prune_removes_stale_directories_without_touching_existing_paths(self):
        kept = self.directory("kept")
        missing = self.directory("missing")
        self.ok("record", "--", kept)
        self.ok("record", "--", missing)
        Path(missing).rmdir()
        self.ok("prune")
        self.assertEqual(self.paths(), [kept])
        result = self.run_cli("record", "relative")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.paths(), [kept])

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_picker_preserves_path_bytes_ignores_ui_overrides_and_handles_cancel(self):
        path = self.directory(" 한글 space\ttab\nnewline\n")
        self.ok("record", "--", path)
        env = {**self.env, "FZF_DEFAULT_OPTS": "--filter=한글 --multi --print-query --tac"}
        result = self.ok("pick", "--null", env=env)
        self.assertEqual(result.stdout, os.fsencode(path) + b"\0")
        self.assertEqual(json.loads(self.ok("pick", "--json", env=env).stdout), path)
        result = self.ok("pick", env={**self.env, "FZF_DEFAULT_OPTS": "--filter=absent"})
        self.assertEqual(result.stdout, b"")
        self.assertEqual(self.paths(), [path])
        self.ok("pick", "--forget", env=env)
        self.assertEqual(self.paths(), [])

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_trash_requires_confirmation_protects_paths_and_retains_failures(self):
        selected = self.directory("trash-me")
        self.ok("record", "--", selected)
        gio = self.bin / "gio"
        gio.write_text(f'#!{sys.executable}\nimport os,pathlib,sys\n'
                       'assert sys.argv[1:3] == ["trash", "--"]\n'
                       'if os.environ.get("TRASH_FAIL"): sys.exit(1)\n'
                       'pathlib.Path(sys.argv[3]).rmdir()\n')
        gio.chmod(0o755)
        env = {**self.env, "FZF_DEFAULT_OPTS": "--filter=trash-me"}
        self.ok("pick", "--delete", input=b"n\n", env=env)
        self.assertTrue(Path(selected).is_dir())
        failed = self.run_cli("pick", "--delete", input=b"y\n", env={**env, "TRASH_FAIL": "1"})
        self.assertEqual(failed.returncode, 2)
        self.assertIn(selected, self.paths())
        self.ok("pick", "--delete", input=b"y\n", env=env)
        self.assertFalse(Path(selected).exists())
        self.assertNotIn(selected, self.paths())
        for path in (str(self.root), str(self.home), os.path.sep):
            self.ok("record", "--", path)
        protected = self.paths()
        self.ok("pick", "--delete", input=b"y\n",
                env={**self.env, "FZF_DEFAULT_OPTS": "--filter=/"})
        self.assertEqual(self.paths(), protected)

    def test_xdg_default_and_relative_value_follow_specification(self):
        self.ok("list", "--json", env={**self.env, "XDG_STATE_HOME": "relative-state"})
        self.assertTrue((self.home / ".local/state/dir-history/history.sqlite3").exists())
        self.assertFalse((self.root / "relative-state").exists())

    @unittest.skipUnless(shutil.which("nu") and shutil.which("fzf"), "requires nu and fzf")
    def test_nushell_navigation_preserves_names_and_can_forget(self):
        path = self.directory(" 한글\ttab\nnewline\n")
        self.ok("record", "--", path)
        adapter = REPO / "private_dot_config/nushell/dir-history.nu"
        prefix = ('def --env cl [directory: string] { cd $"($directory)/" }; '
                  f'source {json.dumps(str(adapter))}; ')
        env = {**self.env, "FZF_DEFAULT_OPTS": "--filter=한글"}
        result = subprocess.run(["nu", "--no-config-file", "-c",
                                 prefix + 'ch; $env.PWD | to json --raw'],
                                cwd=self.root, env=env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), path)
        result = subprocess.run(["nu", "--no-config-file", "-c", prefix + 'chf; vh | to json --raw'],
                                cwd=self.root, env=env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    @unittest.skipUnless(shutil.which("nu"), "requires nu")
    def test_nushell_reload_replaces_legacy_hook_preserves_others_and_exit_status(self):
        target = self.directory("nu hook")
        adapter = REPO / "private_dot_config/nushell/dir-history.nu"
        code = ('def --env cl [directory: string] { cd $directory }; '
                'def _dir_history_init [] { error make {msg: "legacy hook still active"} }; '
                '$env.config.hooks.env_change.PWD = ['
                '{|before after| _dir_history_init }, '
                '{|before after| $env.UNRELATED_HOOK = $after }]; '
                f'source {json.dumps(str(adapter))}; source {json.dumps(str(adapter))}; '
                '$env.LAST_EXIT_CODE = 17; '
                'for hook in $env.config.hooks.env_change.PWD { do --env $hook "before" $env.TARGET }; '
                '{count: ($env.config.hooks.env_change.PWD | length), '
                'status: $env.LAST_EXIT_CODE, unrelated: $env.UNRELATED_HOOK} | to json --raw')
        result = subprocess.run(["nu", "--no-config-file", "-c", code],
                                env={**self.env, "TARGET": target}, cwd=self.root,
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"count": 2, "status": 17, "unrelated": target})
        self.assertEqual(self.paths(), [target])

    @unittest.skipUnless(shutil.which("nu") and shutil.which("fzf"), "requires nu and fzf")
    def test_nushell_trash_confirmation_is_visible_before_answering(self):
        target = self.directory("trash-confirmation")
        self.ok("record", "--", target)
        adapter = REPO / "private_dot_config/nushell/dir-history.nu"
        code = ('def --env cl [directory: string] { cd $directory }; '
                f'source {json.dumps(str(adapter))}; chd')
        process = subprocess.Popen(["nu", "--no-config-file", "-c", code], cwd=self.root,
            env={**self.env, "FZF_DEFAULT_OPTS": "--filter=trash-confirmation"},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = b""
        try:
            deadline = time.monotonic() + 5
            while b"[y/N]" not in output and time.monotonic() < deadline:
                if select.select([process.stderr], [], [], 0.1)[0]:
                    chunk = process.stderr.read1(4096)
                    if not chunk:
                        break
                    output += chunk
            self.assertIn(b"[y/N]", output)
            _, error = process.communicate(input=b"n\n", timeout=5)
            self.assertEqual(process.returncode, 0, error)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        self.assertTrue(Path(target).is_dir())
        self.assertIn(target, self.paths())

    @unittest.skipUnless(shutil.which("fzf"), "requires fzf")
    def test_compatibility_launcher_updates_sqlite_without_nushell(self):
        path = self.directory("compatibility visit")
        launcher = REPO / "private_dot_config/my-scripts/bin/executable_directory-history.nu"
        result = subprocess.run(["bash", str(launcher), "--record", path], env=self.env,
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.paths(), [path])
        output = self.root / "selected"
        result = subprocess.run(["bash", str(launcher), "--output", str(output)],
                                env={**self.env, "FZF_DEFAULT_OPTS": "--filter=compatibility"},
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes(), os.fsencode(path))


if __name__ == "__main__":
    unittest.main()
