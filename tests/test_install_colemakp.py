#!/usr/bin/env python3

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


HELPER = (
    Path(__file__).resolve().parents[1]
    / "private_dot_local/bin/executable_install-colemakp"
)


class InstallColemakpTest(unittest.TestCase):
    def write_executable(self, path: Path, contents: str) -> None:
        path.write_text(textwrap.dedent(contents))
        path.chmod(0o755)

    def make_fixture(self, fixture_root: Path) -> tuple[Path, Path, Path]:
        source_root = fixture_root / "source"
        destination_root = fixture_root / "home"
        fake_bin = fixture_root / "bin"

        for relative_path in (
            "private_dot_config/xkb/symbols/colemakp",
            "private_dot_config/xkb/rules/evdev.xml",
            "private_dot_config/private_kxkbrc",
        ):
            source_file = source_root / relative_path
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text("fixture\n")

        fake_bin.mkdir()
        self.write_executable(
            fake_bin / "xkbcli",
            """
            #!/bin/sh
            exit 0
            """,
        )
        self.write_executable(
            fake_bin / "sha256sum",
            """
            #!/bin/sh
            if [ "${FAKE_LEGACY_HASH:-known}" = known ]; then
                printf '%s  %s\n' \
                    084ea94892840ff31b2738231542aa4ce8440d983f04e77ca64a8b2370bccba4 \
                    "$1"
            else
                printf '%064d  %s\n' 0 "$1"
            fi
            """,
        )
        self.write_executable(
            fake_bin / "chezmoi",
            """
            #!/bin/sh
            set -eu

            case "$1" in
                source-path)
                    printf '%s\n' "$FAKE_SOURCE_ROOT"
                    ;;
                target-path)
                    case "$2" in
                        */xkb/symbols/colemakp)
                            printf '%s\n' "$FAKE_DEST_ROOT/.config/xkb/symbols/colemakp"
                            ;;
                        */xkb/rules/evdev.xml)
                            printf '%s\n' "$FAKE_DEST_ROOT/.config/xkb/rules/evdev.xml"
                            ;;
                        */private_kxkbrc)
                            printf '%s\n' "$FAKE_DEST_ROOT/.config/kxkbrc"
                            ;;
                        *) exit 3 ;;
                    esac
                    ;;
                apply)
                    printf '%s\n' "$*" > "$FAKE_APPLY_LOG"
                    if [ "${FAKE_APPLY_FAIL:-false}" = true ]; then
                        exit 9
                    fi
                    for argument in "$@"; do
                        case "$argument" in
                            /*)
                                mkdir -p "$(dirname "$argument")"
                                : > "$argument"
                                ;;
                        esac
                    done
                    ;;
                *) exit 4 ;;
            esac
            """,
        )

        return source_root, destination_root, fake_bin

    def run_helper(
        self,
        arguments: list[str],
        *,
        legacy: bool = False,
        known_legacy: bool = True,
        apply_fails: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        fixture_root = Path(temporary_directory.name)
        source_root, destination_root, fake_bin = self.make_fixture(fixture_root)
        legacy_path = destination_root / ".config/xkb/symbols/us"
        if legacy:
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.write_text("legacy layout\n")

        apply_log = fixture_root / "apply.log"
        environment = os.environ.copy()
        environment.update(
            {
                "FAKE_APPLY_FAIL": "true" if apply_fails else "false",
                "FAKE_APPLY_LOG": str(apply_log),
                "FAKE_DEST_ROOT": str(destination_root),
                "FAKE_LEGACY_HASH": "known" if known_legacy else "unknown",
                "FAKE_SOURCE_ROOT": str(source_root),
                "PATH": f"{fake_bin}:/usr/bin:/bin",
            }
        )
        result = subprocess.run(
            ["/bin/bash", HELPER, *arguments],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )
        return result, destination_root, apply_log

    def test_dry_run_preserves_legacy_file(self) -> None:
        result, destination_root, apply_log = self.run_helper(
            ["--dry-run"], legacy=True
        )

        legacy_path = destination_root / ".config/xkb/symbols/us"
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(legacy_path.exists())
        self.assertFalse(
            legacy_path.with_name("us.pre-standalone-colemakp").exists()
        )
        self.assertIn("Would move", result.stdout)
        self.assertIn("--dry-run --verbose", apply_log.read_text())

    def test_install_moves_known_legacy_file_and_applies_layout(self) -> None:
        result, destination_root, _apply_log = self.run_helper([], legacy=True)

        symbols_dir = destination_root / ".config/xkb/symbols"
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((symbols_dir / "us").exists())
        self.assertTrue((symbols_dir / "us.pre-standalone-colemakp").exists())
        self.assertTrue((symbols_dir / "colemakp").exists())

    def test_install_refuses_unknown_us_symbols_file(self) -> None:
        result, destination_root, apply_log = self.run_helper(
            [], legacy=True, known_legacy=False
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to replace", result.stderr)
        self.assertTrue((destination_root / ".config/xkb/symbols/us").exists())
        self.assertFalse(apply_log.exists())

    def test_apply_failure_restores_legacy_file(self) -> None:
        result, destination_root, _apply_log = self.run_helper(
            [], legacy=True, apply_fails=True
        )

        symbols_dir = destination_root / ".config/xkb/symbols"
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((symbols_dir / "us").exists())
        self.assertFalse((symbols_dir / "us.pre-standalone-colemakp").exists())
        self.assertIn("restored legacy XKB file", result.stderr)


if __name__ == "__main__":
    unittest.main()
