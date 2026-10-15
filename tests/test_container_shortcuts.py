"""Exercise container shortcuts with real sudo, without prompts or elevation."""

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
SCRIPTS = ROOT / "private_dot_config/my-scripts"
SOCKET = "unix:///run/podman/podman.sock"


class ContainerShortcutsRealSudoTests(unittest.TestCase):
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
        temporary = tempfile.TemporaryDirectory(prefix="container-shortcuts-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "tools with spaces"
        self.bin.mkdir()
        for name in ("sudo-path", "lazydocker-with-podman"):
            target = self.bin / name
            shutil.copyfile(SCRIPTS / "bin" / ("executable_" + name), target)
            target.chmod(0o755)
        self.calls = self.root / "sudo-called"
        sudo = self.bin / "sudo"
        # Preserve real sudo's parser, but always request the invoking user.
        sudo.write_text(
            f"#!{sys.executable}\n"
            "import os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['SUDO_PATH_CALLS']).touch()\n"
            f"os.execv({self.sudo!r}, [{self.sudo!r}, '-n', '-u', {self.user!r}, *sys.argv[1:]])\n"
        )
        sudo.chmod(0o755)
        self.lazydocker = self.bin / "lazydocker"
        self.lazydocker.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "print(json.dumps({'args': sys.argv[1:], "
            "'host': os.environ.get('DOCKER_HOST'), 'uid': os.geteuid(), "
            "'path': os.environ.get('PATH')}))\n"
            "sys.exit(23 if sys.argv[1:] == ['--test-exit-23'] else 0)\n"
        )
        self.lazydocker.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.bin), "SUDO_PATH_CALLS": str(self.calls)}
        self.env.pop("DOCKER_HOST", None)

    def run_command(self, command, *args, path=None, cwd=None):
        env = dict(self.env)
        if path is not None:
            env["PATH"] = path
        return subprocess.run(
            [str(self.bin / command), *args], cwd=cwd or self.root, env=env,
            capture_output=True, text=True, timeout=10,
        )

    def assert_result(self, result, args, host=SOCKET, path=None):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "args": args, "host": host, "uid": os.getuid(),
            "path": str(self.bin) if path is None else path,
        })

    def test_socket_and_arguments_through_real_sudo(self):
        args = ["--help", "space argument", "", "한글", "$(touch never)"]
        result = self.run_command("sudo-path", "lazydocker-with-podman", *args)
        self.assert_result(result, args)
        self.assertTrue(self.calls.exists())

    def test_podman_without_sudo(self):
        self.env["DOCKER_HOST"] = "wrong-socket"
        result = self.run_command("lazydocker-with-podman", "space argument")
        self.assert_result(result, ["space argument"])
        self.assertFalse(self.calls.exists())

    def test_relative_and_current_directory_path_entries(self):
        for path, cwd in ((self.bin.name, self.root), (".", self.bin), ("", self.bin)):
            with self.subTest(path=path):
                result = self.run_command("sudo-path", "lazydocker-with-podman", path=path, cwd=cwd)
                self.assert_result(result, [], path=path)

    def test_explicit_paths_and_external_builtin_names(self):
        for command in (str(self.lazydocker), str(Path(self.bin.name) / "lazydocker")):
            with self.subTest(command=command):
                self.assert_result(self.run_command("sudo-path", command), [], host=None)
        # A generic helper must find the external executable even for a builtin name.
        shutil.copyfile(self.lazydocker, self.bin / "printf")
        (self.bin / "printf").chmod(0o755)
        self.assert_result(self.run_command("sudo-path", "printf"), [], host=None)

    def test_lazydocker_exit_status(self):
        result = self.run_command("sudo-path", "lazydocker-with-podman", "--test-exit-23")
        self.assertEqual(result.returncode, 23, result.stderr)

    def test_missing_lazydocker(self):
        self.lazydocker.unlink()
        result = self.run_command("lazydocker-with-podman")
        self.assertEqual(result.returncode, 127, result.stderr)
        self.assertIn("lazydocker", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_sudo_path_usage_and_missing_executables(self):
        self.assertEqual(self.run_command("sudo-path").returncode, 2)
        (self.bin / "directory-command").mkdir()
        for command in ("missing-command", "directory-command", "./missing-command", ""):
            with self.subTest(command=command):
                result = self.run_command("sudo-path", command)
                self.assertEqual(result.returncode, 127, result.stderr)
                self.assertIn("executable not found", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_aliases_in_bash_zsh_and_nushell(self):
        aliases = (ROOT / "private_dot_config/nushell/alias.nu").read_text()
        nu_aliases = "\n".join(line for line in aliases.splitlines() if line.startswith(
            ("alias lzd =", "alias lzds =", "alias lzp =", "alias lzps =")
        ))
        args = ["--help", "space argument", "", "한글", "$(touch never)"]
        for shell in ("bash", "zsh", "nu"):
            executable = shutil.which(shell)
            if not executable:
                continue
            for shortcut, host, uses_sudo in (
                ("lzd", None, False), ("lzds", None, True),
                ("lzp", SOCKET, False), ("lzps", SOCKET, True),
            ):
                with self.subTest(shell=shell, shortcut=shortcut):
                    self.calls.unlink(missing_ok=True)
                    invocation = shlex.join([shortcut, *args])
                    env = {**self.env, "SHORTCUT_COMMAND": invocation,
                           "SHORTCUT_SOURCE": str(SCRIPTS / "shell/productivity.sh")}
                    if shell == "nu":
                        command = [executable, "--no-config-file", "-c", nu_aliases + "\n" + invocation]
                    else:
                        flags = ["--noprofile", "--norc"] if shell == "bash" else ["-f"]
                        setup = "shopt -s expand_aliases; " if shell == "bash" else ""
                        command = [executable, *flags, "-c", setup +
                                   'source "$SHORTCUT_SOURCE"; eval "$SHORTCUT_COMMAND"']
                    result = subprocess.run(command, cwd=self.root, env=env,
                                            capture_output=True, text=True, timeout=10)
                    self.assert_result(result, args, host=host)
                    self.assertEqual(self.calls.exists(), uses_sudo)


if __name__ == "__main__":
    unittest.main()
