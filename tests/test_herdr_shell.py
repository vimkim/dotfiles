#!/usr/bin/env python3

import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

HERDR_SHELL = (
    Path(__file__).resolve().parents[1] / "private_dot_local/bin/executable_herdr-shell"
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
        reporter_succeeds: bool = True,
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
            for shell_name in ("bash", "zsh", "nu"):
                self.write_executable(
                    fixture_directory / shell_name,
                    f"""
                    #!/bin/sh
                    printf 'LAUNCHED_SHELL={shell_name}\\n'
                    printf 'HERDR_SHELL=%s\\n' "${{HERDR_SHELL-<unset>}}"
                    printf 'DISPLAY=%s\\n' "${{DISPLAY-<unset>}}"
                    printf 'WAYLAND_DISPLAY=%s\\n' "${{WAYLAND_DISPLAY-<unset>}}"
                    printf 'XAUTHORITY=%s\\n' "${{XAUTHORITY-<unset>}}"
                    printf 'XDG_RUNTIME_DIR=%s\\n' "${{XDG_RUNTIME_DIR-<unset>}}"
                    printf 'XDG_SESSION_TYPE=%s\\n' "${{XDG_SESSION_TYPE-<unset>}}"
                    """,
                )
            self.write_executable(
                fixture_directory / "herdr-tab-status",
                f"""
                #!/bin/sh
                printf '%s\\n' "$*" >> "$HERDR_STATUS_TEST_LOG"
                exit {0 if reporter_succeeds else 1}
                """,
            )

            environment = {
                "HOME": str(fixture_directory),
                "PATH": f"{fixture_directory}:/usr/bin:/bin",
                "HERDR_STATUS_TEST_LOG": str(fixture_directory / "reporter-calls"),
            }
            environment.update(inherited_environment or {})
            self.fixture_directory = fixture_directory
            result = subprocess.run(
                ["/bin/sh", HERDR_SHELL],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
            )
            calls = fixture_directory / "reporter-calls"
            self.reporter_calls = (
                calls.read_text().splitlines() if calls.exists() else []
            )
            return result

    def parse_output(self, result: subprocess.CompletedProcess[str]) -> dict[str, str]:
        self.assertEqual(result.returncode, 0, result.stderr)
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def parse_environment(
        self, result: subprocess.CompletedProcess[str]
    ) -> dict[str, str]:
        parsed = self.parse_output(result)
        return {name: parsed[name] for name in GRAPHICAL_ENVIRONMENT}

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

    def test_starts_status_reporter_inside_herdr_before_shell(self) -> None:
        result = self.run_shell(
            {"HERDR_ENV": "1", "HERDR_SOCKET_PATH": "/tmp/example-herdr.sock"}
        )
        self.parse_environment(result)
        self.assertEqual(self.reporter_calls, ["start"])

    def test_reporter_failure_does_not_prevent_shell_start(self) -> None:
        result = self.run_shell(
            {"HERDR_ENV": "1", "HERDR_SOCKET_PATH": "/tmp/example-herdr.sock"},
            reporter_succeeds=False,
        )
        self.parse_environment(result)
        self.assertEqual(self.reporter_calls, ["start"])

    def test_does_not_start_reporter_without_session_context(self) -> None:
        result = self.run_shell({"HERDR_ENV": "1"})
        self.parse_environment(result)
        self.assertEqual(self.reporter_calls, [])

    def test_defaults_to_bash_even_when_zsh_and_nu_exist(self) -> None:
        parsed = self.parse_output(self.run_shell())
        self.assertEqual(parsed["LAUNCHED_SHELL"], "bash")
        self.assertEqual(parsed["HERDR_SHELL"], "<unset>")

    def test_herdr_shell_override_launches_requested_shell_and_unsets_var(self) -> None:
        parsed = self.parse_output(self.run_shell({"HERDR_SHELL": "nu"}))
        self.assertEqual(parsed["LAUNCHED_SHELL"], "nu")
        self.assertEqual(parsed["HERDR_SHELL"], "<unset>")

    def test_herdr_shell_override_accepts_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as extra_dir:
            custom_nu = Path(extra_dir) / "nu"
            custom_nu.write_text(
                "#!/bin/sh\n"
                "printf 'LAUNCHED_SHELL=custom-nu\\n'\n"
                "printf 'HERDR_SHELL=%s\\n' \"${HERDR_SHELL-<unset>}\"\n"
            )
            custom_nu.chmod(0o755)
            parsed = self.parse_output(self.run_shell({"HERDR_SHELL": str(custom_nu)}))
            self.assertEqual(parsed["LAUNCHED_SHELL"], "custom-nu")
            self.assertEqual(parsed["HERDR_SHELL"], "<unset>")

    def test_unresolvable_herdr_shell_falls_back_to_bash_and_unsets_var(self) -> None:
        parsed = self.parse_output(
            self.run_shell({"HERDR_SHELL": "nonexistent-shell-xyz"})
        )
        self.assertEqual(parsed["LAUNCHED_SHELL"], "bash")
        self.assertEqual(parsed["HERDR_SHELL"], "<unset>")


if __name__ == "__main__":
    unittest.main()
