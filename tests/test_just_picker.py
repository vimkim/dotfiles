"""Exercise just picker choices with a real justfile."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PICKER = Path(__file__).resolve().parents[1] / "private_dot_config/my-scripts/bin/executable_just-pick-and-print.nu"


@unittest.skipUnless(all(shutil.which(name) for name in ("nu", "just")), "requires nu and just")
class JustPickerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.justfile = self.root / "justfile"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fzf = self.bin / "fzf"
        fzf.write_text('#!/bin/sh\ncat > "$CHOICES"\n'
                       'if [ -n "$SELECTION" ]; then grep -Fx -- "$SELECTION" "$CHOICES" || :; fi\n')
        fzf.chmod(0o755)
        self.choices = self.root / "choices"

    def pick(self, selection=""):
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}",
               "CHOICES": str(self.choices), "SELECTION": selection}
        result = subprocess.run(["nu", str(PICKER), "-f", str(self.justfile), "-d", str(self.root)],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout, self.choices.read_text().splitlines()

    def test_public_aliases_follow_targets_and_selected_alias_is_printed(self):
        self.justfile.write_text('''alias z := build
alias b := build
alias d := default
[private]
alias hidden := build
alias _hidden := build
alias secret-alias := secret

build:
    @echo build

[default]
default:
    @echo default

[private]
secret:
    @echo secret

last:
    @echo last
''')
        output, choices = self.pick("b")
        self.assertEqual(choices, ["default", "d", "build", "b", "z", "last"])
        self.assertEqual(output, "b\n")

    def test_no_aliases_and_cancellation(self):
        self.justfile.write_text('first:\n    @echo first\n\nsecond:\n    @echo second\n')
        output, choices = self.pick()
        self.assertEqual(choices, ["first", "second"])
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()
