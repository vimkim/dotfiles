#!/usr/bin/env python3

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


HERDR_SHELL = (
    Path(__file__).resolve().parents[1]
    / "private_dot_local/bin/executable_herdr-shell"
)

GRAPHICAL_ENVIRONMENT = {
    "DISPLAY": ":99",
    "WAYLAND_DISPLAY": "wayland-test",
    "XAUTHORITY": "/tmp/test-xauthority",
    "XDG_RUNTIME_DIR": "/run/user/test",
    "XDG_SESSION_TYPE": "wayland",
}


class HerdrShellTest(unittest.TestCase):
    def write_executable(self, path: Path, contents: str) -> None:
        path.write_text(textwrap.dedent(contents))
        path.chmod(0o755)

    def run_shell(
        self,
        inherited_environment: dict[str, str] | None = None,
        systemctl_succeeds: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_directory = Path(temporary_directory)
            manager_environment = "\n".join(
                f"{name}={value}" for name, value in GRAPHICAL_ENVIRONMENT.items()
            )
            systemctl_body = (
                f"printf '%s\\n' '{manager_environment}'"
                if systemctl_succeeds
                else "exit 1"
            )
            self.write_executable(
                fixture_directory / "systemctl",
                f"""
                #!/bin/sh
                [ "$1" = "--user" ] && [ "$2" = "show-environment" ] || exit 2
                {systemctl_body}
                """,
            )
            self.write_executable(
                fixture_directory / "nu",
                """
                #!/bin/sh
                printf 'DISPLAY=%s\n' "${DISPLAY-<unset>}"
                printf 'WAYLAND_DISPLAY=%s\n' "${WAYLAND_DISPLAY-<unset>}"
                printf 'XAUTHORITY=%s\n' "${XAUTHORITY-<unset>}"
                printf 'XDG_RUNTIME_DIR=%s\n' "${XDG_RUNTIME_DIR-<unset>}"
                printf 'XDG_SESSION_TYPE=%s\n' "${XDG_SESSION_TYPE-<unset>}"
                """,
            )

            environment = {
                "HOME": str(fixture_directory),
                "PATH": f"{fixture_directory}:/usr/bin:/bin",
            }
            environment.update(inherited_environment or {})
            return subprocess.run(
                ["/bin/sh", HERDR_SHELL],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
            )

    def parse_environment(
        self, result: subprocess.CompletedProcess[str]
    ) -> dict[str, str]:
        self.assertEqual(result.returncode, 0, result.stderr)
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def test_imports_missing_graphical_environment_from_user_manager(self) -> None:
        result = self.run_shell()

        self.assertEqual(self.parse_environment(result), GRAPHICAL_ENVIRONMENT)

    def test_preserves_inherited_graphical_environment(self) -> None:
        inherited_environment = {
            "DISPLAY": "localhost:10.0",
            "WAYLAND_DISPLAY": "forwarded-wayland",
            "XAUTHORITY": "/tmp/forwarded-xauthority",
            "XDG_RUNTIME_DIR": "/run/user/forwarded",
            "XDG_SESSION_TYPE": "tty",
        }

        result = self.run_shell(inherited_environment)

        self.assertEqual(self.parse_environment(result), inherited_environment)

    def test_still_launches_shell_when_user_manager_is_unavailable(self) -> None:
        result = self.run_shell(systemctl_succeeds=False)

        self.assertEqual(
            self.parse_environment(result),
            {name: "<unset>" for name in GRAPHICAL_ENVIRONMENT},
        )


if __name__ == "__main__":
    unittest.main()
