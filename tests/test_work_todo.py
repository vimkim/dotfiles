"""Run with python3 -m unittest discover -s tests -p test_work_todo.py."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "private_dot_config/my-scripts/bin/executable_work-todo"


class TodoWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "work-todo").symlink_to(SOURCE)
        for name in ("todo-today", "todo-3days", "todo-5days"):
            (self.root / name).symlink_to("work-todo")
        fake = self.root / "work-tracker"
        fake.write_text("#!/usr/bin/env python3\nimport json, os, sys\nprint(json.dumps(sys.argv[1:]))\nprint('stderr preserved', file=sys.stderr)\nsys.exit(int(os.environ.get('FAKE_EXIT', '0')))\n")
        fake.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"]}

    def run_alias(self, name, *args):
        return subprocess.run([str(self.root / name), *args], env=self.env, text=True, capture_output=True)

    def test_horizons_and_global_options(self):
        for name, preset in (("todo-today", ["today"]), ("todo-3days", ["--days", "3"]), ("todo-5days", ["--days", "5"])):
            result = self.run_alias(name, "--json", "--database", "a path/ledger.db")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout), ["todo", *preset, "--json", "--database", "a path/ledger.db"])
            self.assertIn("stderr preserved", result.stderr)
        result = self.run_alias("todo-today", "--database", "--days")
        self.assertEqual(result.returncode, 0)

    def test_reject_horizon_override_and_unknown_arguments(self):
        for args in (("--days", "4"), ("--days=5",), ("--day", "3"), ("today",), ("--database",)):
            self.assertEqual(self.run_alias("todo-3days", *args).returncode, 2)

    def test_direct_dispatch_and_exit_propagation(self):
        self.env["FAKE_EXIT"] = "7"
        result = self.run_alias("work-todo", "--days", "8", "--json")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(json.loads(result.stdout), ["todo", "--days", "8", "--json"])

    def test_missing_binary(self):
        (self.root / "work-tracker").unlink()
        (self.root / "python3").symlink_to(os.sys.executable)
        self.env["PATH"] = str(self.root)
        result = self.run_alias("todo-today")
        self.assertEqual(result.returncode, 127)
        self.assertIn("not installed", result.stderr)


if __name__ == "__main__":
    unittest.main()
