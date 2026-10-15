"""Exercise sudo argument parsing as the invoking user, without prompts or elevation."""

import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "private_dot_config/my-scripts/bin/executable_lzps"
SOCKET = "unix:///run/podman/podman.sock"


class LzpsRealSudoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sudo = shutil.which("sudo")
        true = shutil.which("true")
        if not cls.sudo or not true:
            raise unittest.SkipTest("sudo and true are required for the parser regression")
        cls.user = pwd.getpwuid(os.getuid()).pw_name
        result = subprocess.run(
            [cls.sudo, "-n", "-u", cls.user, true],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode:
            raise unittest.SkipTest("sudo cannot run as the invoking user without a prompt")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="lzps-check-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "tools with spaces"
        self.bin.mkdir()
        sudo = self.bin / "sudo"
        # Preserve real sudo's parser, but always request the invoking user.
        sudo.write_text(
            f"#!/bin/sh\nexec {shlex.quote(self.sudo)} -n "
            f"-u {shlex.quote(self.user)} \"$@\"\n"
        )
        sudo.chmod(0o755)
        self.lazydocker = self.bin / "lazydocker"
        self.lazydocker.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "print(json.dumps({'args': sys.argv[1:], "
            "'host': os.environ.get('DOCKER_HOST'), 'uid': os.geteuid()}))\n"
            "sys.exit(23 if sys.argv[1:] == ['--test-exit-23'] else 0)\n"
        )
        self.lazydocker.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.bin), "DOCKER_HOST": "wrong-socket"}

    def run_wrapper(self, *args, path=None, cwd=None):
        env = dict(self.env)
        if path is not None:
            env["PATH"] = path
        return subprocess.run(
            [str(WRAPPER), *args], cwd=cwd or self.root, env=env,
            capture_output=True, text=True, timeout=10,
        )

    def test_socket_and_arguments_through_real_sudo(self):
        args = ["--help", "space argument", "", "한글", "$(touch never)"]
        result = self.run_wrapper(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "args": args, "host": SOCKET, "uid": os.getuid(),
        })

    def test_relative_and_current_directory_path_entries(self):
        for path, cwd in ((self.bin.name, self.root), (".", self.bin), ("", self.bin)):
            with self.subTest(path=path):
                result = self.run_wrapper(path=path, cwd=cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {
                    "args": [], "host": SOCKET, "uid": os.getuid(),
                })

    def test_lazydocker_exit_status(self):
        result = self.run_wrapper("--test-exit-23")
        self.assertEqual(result.returncode, 23, result.stderr)

    def test_missing_lazydocker(self):
        self.lazydocker.unlink()
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 127, result.stderr)
        self.assertEqual(result.stderr, "lzps: lazydocker was not found in PATH.\n")


if __name__ == "__main__":
    unittest.main()
