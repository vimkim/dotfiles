#!/usr/bin/env python3

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render_template(path: Path) -> str:
    text = path.read_text()
    chezmoi = shutil.which("chezmoi")
    if chezmoi:
        result = subprocess.run(
            [chezmoi, "--source", str(ROOT), "execute-template"],
            input=text,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    # Fallback when chezmoi is unavailable in a minimal test environment.
    text = re.sub(r"\{\{\s*template\s+\"deeptutor-env\.sh\"\s+\.\s*\}\}", "", text)
    return text.replace("{{ .chezmoi.homeDir }}", "$HOME")


class ShellPathTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".config/my-scripts/bin").mkdir(parents=True)
        (self.home / ".cargo/bin").mkdir(parents=True)

        shutil.copyfile(ROOT / "dot_bash_profile", self.home / ".bash_profile")
        shutil.copyfile(ROOT / "dot_bashrc", self.home / ".bashrc")
        shutil.copyfile(ROOT / "dot_zshrc", self.home / ".zshrc")
        (self.home / ".profile").write_text(render_template(ROOT / "dot_profile.tmpl"))
        (self.home / ".zshenv").write_text(render_template(ROOT / "dot_zshenv.tmpl"))

        self.bash = shutil.which("bash") or "/bin/bash"
        self.sh = shutil.which("sh") or "/bin/sh"
        self.zsh = shutil.which("zsh")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def base_env(self, extra_path: list[str] | None = None) -> dict[str, str]:
        path_parts = [*(extra_path or []), "/usr/local/bin", "/usr/bin", "/bin"]
        return {
            "HOME": str(self.home),
            "ZDOTDIR": str(self.home),
            "USER": os.environ.get("USER", "tester"),
            "PATH": os.pathsep.join(path_parts),
        }

    def run_shell(
        self,
        argv: list[str],
        extra_path: list[str] | None = None,
    ) -> list[str]:
        result = subprocess.run(
            argv,
            env=self.base_env(extra_path=extra_path),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"{argv} failed: {result.stderr}")
        self.assertEqual(result.stderr, "", f"{argv} wrote stderr: {result.stderr}")
        return result.stdout.strip().split(os.pathsep)

    def test_includes_my_cubrid_bin_when_directory_exists(self) -> None:
        cubrid_bin = self.home / "my-cubrid/bin"
        cubrid_bin.mkdir(parents=True)
        local_bin = str(self.home / ".local/bin")
        cubrid_bin_str = str(cubrid_bin)

        cases: list[tuple[str, list[str], bool]] = [
            ("bash -lc", [self.bash, "-lc", 'printf "%s\n" "$PATH"'], True),
            ("bash -ic", [self.bash, "-ic", 'printf "%s\n" "$PATH"'], True),
            ("sh -lc", [self.sh, "-lc", 'printf "%s\n" "$PATH"'], True),
        ]
        if self.zsh:
            cases.append(("zsh -c", [self.zsh, "-c", 'printf "%s\n" "$PATH"'], False))
            cases.append(
                (
                    "zsh -fc source .zshrc",
                    [self.zsh, "-fc", 'source "$HOME/.zshrc" && printf "%s\n" "$PATH"'],
                    False,
                )
            )

        for label, argv, check_local_precedence in cases:
            with self.subTest(shell=label):
                entries = self.run_shell(argv)
                self.assertEqual(entries.count(cubrid_bin_str), 1, entries)
                if check_local_precedence:
                    self.assertIn(local_bin, entries)
                    self.assertLess(
                        entries.index(local_bin),
                        entries.index(cubrid_bin_str),
                        entries,
                    )

    def test_omits_my_cubrid_bin_when_directory_absent(self) -> None:
        cubrid_bin_str = str(self.home / "my-cubrid/bin")
        cases: list[tuple[str, list[str]]] = [
            ("bash -lc", [self.bash, "-lc", 'printf "%s\n" "$PATH"']),
            ("bash -ic", [self.bash, "-ic", 'printf "%s\n" "$PATH"']),
            ("sh -lc", [self.sh, "-lc", 'printf "%s\n" "$PATH"']),
        ]
        if self.zsh:
            cases.append(("zsh -c", [self.zsh, "-c", 'printf "%s\n" "$PATH"']))
            cases.append(
                (
                    "zsh -fc source .zshrc",
                    [self.zsh, "-fc", 'source "$HOME/.zshrc" && printf "%s\n" "$PATH"'],
                )
            )

        for label, argv in cases:
            with self.subTest(shell=label):
                entries = self.run_shell(argv)
                self.assertNotIn(cubrid_bin_str, entries)

    def test_deduplicates_my_cubrid_bin_when_already_on_path(self) -> None:
        cubrid_bin = self.home / "my-cubrid/bin"
        cubrid_bin.mkdir(parents=True)
        cubrid_bin_str = str(cubrid_bin)

        cases: list[tuple[str, list[str]]] = [
            ("bash -lc", [self.bash, "-lc", 'printf "%s\n" "$PATH"']),
            ("bash -ic", [self.bash, "-ic", 'printf "%s\n" "$PATH"']),
            ("sh -lc", [self.sh, "-lc", 'printf "%s\n" "$PATH"']),
        ]
        if self.zsh:
            cases.append(("zsh -c", [self.zsh, "-c", 'printf "%s\n" "$PATH"']))
            cases.append(
                (
                    "zsh -fc source .zshrc",
                    [self.zsh, "-fc", 'source "$HOME/.zshrc" && printf "%s\n" "$PATH"'],
                )
            )

        for label, argv in cases:
            with self.subTest(shell=label):
                entries = self.run_shell(argv, extra_path=[cubrid_bin_str])
                self.assertEqual(entries.count(cubrid_bin_str), 1, entries)


if __name__ == "__main__":
    unittest.main()
