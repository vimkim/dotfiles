#!/usr/bin/env python3
"""Prove check.py can fail: break the real herdr-tab-status in known ways.

Each mutant replaces one exact snippet of private_dot_local/bin/executable_herdr-tab-status
in a temporary copy, then runs check.py (all faults) on that copy. Every mutant
must FAIL. A mutant whose snippet no longer exists is STALE: update its snippet to
the current code so it breaks the same rule again.

Usage: mutants.py [--depth N] [NAME ...]
Exit status: 0 when every selected mutant is caught, 1 otherwise.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[2] / "private_dot_local/bin/executable_herdr-tab-status"

# name: (rule it breaks, exact old snippet, replacement)
MUTANTS = {
    "rename-before-save": (
        "update() renames tabs without first saving the journal",
        "            try:\n                self.save()\n            except BaseException:\n                self.tabs = previous\n                raise\n",
        "            pass\n",
    ),
    "keep-unsaved-journal": (
        "a failed save leaves the unsaved journal in memory, so the retry skips the save (finding F1)",
        "                self.tabs = previous\n",
        "                pass\n",
    ),
    "forget-current-label": (
        "the journal stops remembering the label Herdr currently shows",
        '                labels.append(tab["current"])\n',
        "                pass\n",
    ),
    "forget-old-suffixes": (
        "the journal drops older status suffixes still on screen",
        '                suffixes.extend(\n                    suffix\n                    for suffix in previous["suffixes"]\n                    if tab["current"].endswith(suffix)\n                )\n',
        "                pass\n",
    ),
    "keep-number-prefix": (
        "original_label stops removing the managed number from an edited name",
        "                        base = base[len(prefix) :]\n",
        "                        pass\n",
    ),
    "restore-keeps-journal": (
        "restore() leaves the journal records on disk",
        "        self.tabs = {}\n        self.save()\n",
        "        pass\n",
    ),
    "restore-skips-renames": (
        "restore() leaves decorated labels in place",
        '        for tab in snapshot["tabs"]:\n            base, owned = original_label(tab["label"], self.tabs.get(tab["tab_id"]))\n            if owned:\n',
        '        for tab in snapshot["tabs"]:\n            base, owned = original_label(tab["label"], self.tabs.get(tab["tab_id"]))\n            if False:\n',
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("names", nargs="*", choices=[[], *MUTANTS], default=[])
    args = parser.parse_args()
    source = SCRIPT.read_text()
    failed = 0
    for name in args.names or MUTANTS:
        rule, old, new = MUTANTS[name]
        if source.count(old) != 1:
            print(f"STALE   {name}: snippet not found exactly once; rule: {rule}")
            failed = 1
            continue
        with tempfile.TemporaryDirectory() as scratch:
            copy = Path(scratch) / "herdr-tab-status"
            copy.write_text(source.replace(old, new))
            result = subprocess.run(
                [sys.executable, str(HERE / "check.py"),
                 "--depth", str(args.depth), "--script", str(copy)],
                capture_output=True, text=True,
            )
        first = result.stdout.splitlines()[0] if result.stdout else result.stderr.strip()
        if result.returncode == 1 and first.startswith("FAIL"):
            print(f"CAUGHT  {name}: {first[5:]}")
        else:
            print(f"MISSED  {name} ({rule}): {first}")
            failed = 1
    return failed


if __name__ == "__main__":
    sys.exit(main())
