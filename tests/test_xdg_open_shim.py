#!/usr/bin/env python3

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "private_dot_local/bin"


class XdgOpenShimTest(unittest.TestCase):
    def run_shim(self, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            shim_dir = root / "local-bin"
            system_dir = root / "system-bin"
            shim_dir.mkdir()
            system_dir.mkdir()
            shutil.copy(BIN / "executable_xdg-open", shim_dir / "xdg-open")
            (shim_dir / "xdg-open").chmod(0o755)
            for path, label in (
                (shim_dir / "no-browser", "blocked"),
                (system_dir / "xdg-open", "system"),
            ):
                path.write_text(
                    textwrap.dedent(
                        f"""\
                        #!/bin/sh
                        printf '{label} %s\\n' "$*"
                        """
                    )
                )
                path.chmod(0o755)
            env = {
                "PATH": f"{shim_dir}:{system_dir}:/usr/bin:/bin",
                "HOME": str(root),
                **environment,
            }
            return subprocess.run(
                ["xdg-open", "https://example.com/x"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_blocks_over_ssh(self) -> None:
        result = self.run_shim({"SSH_CONNECTION": "1.2.3.4 1 5.6.7.8 22", "DISPLAY": ":0"})
        self.assertEqual(result.stdout, "blocked https://example.com/x\n")

    def test_blocks_forwarded_display_without_ssh_variables(self) -> None:
        result = self.run_shim({"DISPLAY": "localhost:10.0"})
        self.assertEqual(result.stdout, "blocked https://example.com/x\n")

    def test_passes_through_on_local_desktop(self) -> None:
        result = self.run_shim({"DISPLAY": ":0"})
        self.assertEqual(result.stdout, "system https://example.com/x\n")

    def test_passes_through_without_display(self) -> None:
        result = self.run_shim({})
        self.assertEqual(result.stdout, "system https://example.com/x\n")


if __name__ == "__main__":
    unittest.main()
