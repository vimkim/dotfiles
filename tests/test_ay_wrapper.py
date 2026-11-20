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

if sys.argv[1:] == ["--version"]:
    if os.environ.get("AY_FAIL_VERSION") == "1":
        sys.exit(1)
    print("9.9.9")
    sys.exit(0)

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

    def run_ay(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        stdin: str = "",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), *args],
            input=stdin,
            env=self.env if env is None else env,
            text=True,
            capture_output=True,
            timeout=4,
            check=False,
        )

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
        result = self.run_ay(*args, stdin="piped input")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            json.loads(result.stdout),
            {
                "args": ["--dangerously-skip-permissions", *args],
                "input": "piped input",
            },
        )

    def test_help_describes_wrapper_without_running_agy(self) -> None:
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                result = self.run_ay(flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertIn("usage: ay [AGY_ARGS...]", result.stdout)
                self.assertIn("Antigravity CLI", result.stdout)
                self.assertIn('exec agy --dangerously-skip-permissions "$@"', result.stdout)
                self.assertIn("ay -- --help", result.stdout)
                self.assertFalse(result.stdout.lstrip().startswith("{"))

    def test_version_describes_wrapper_and_agy_version(self) -> None:
        result = self.run_ay("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "ay: exec wrapper for agy --dangerously-skip-permissions (agy 9.9.9)\n",
        )

    def test_version_handles_failing_or_missing_agy(self) -> None:
        expected = (
            "ay: exec wrapper for agy --dangerously-skip-permissions "
            "(agy version unavailable)\n"
        )
        for label, extra_env in (
            ("failing", {**self.env, "AY_FAIL_VERSION": "1"}),
            ("missing", {**self.env, "PATH": "/usr/bin:/bin"}),
        ):
            with self.subTest(case=label):
                result = self.run_ay("--version", env=extra_env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(result.stdout, expected)

    def test_double_dash_passes_help_and_version_to_agy(self) -> None:
        for flag in ("--help", "--version"):
            with self.subTest(flag=flag):
                result = self.run_ay("--", flag)
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(
                    json.loads(result.stdout),
                    {
                        "args": ["--dangerously-skip-permissions", flag],
                        "input": "",
                    },
                )

    def test_subcommand_help_passes_through_to_agy(self) -> None:
        result = self.run_ay("models", "--help")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            json.loads(result.stdout),
            {
                "args": ["--dangerously-skip-permissions", "models", "--help"],
                "input": "",
            },
        )


if __name__ == "__main__":
    unittest.main()
