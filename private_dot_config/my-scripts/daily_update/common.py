"""Subprocess execution and independent step results."""

import shlex
import subprocess
from dataclasses import dataclass, field


class Skipped(Exception):
    """Work was preserved or a prerequisite was unavailable."""


class Failed(Exception):
    """An attempted operation failed."""


def print_command(*args):
    print(f"   $ {shlex.join(map(str, args))}", flush=True)


def command(*args, cwd=None, capture=True):
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        text=True,
        check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def checked(*args, reason, cwd=None, capture=True):
    result = command(*args, cwd=cwd, capture=capture)
    if result.returncode:
        if capture and result.stderr:
            print(result.stderr.rstrip(), flush=True)
        raise Failed(reason)
    return result.stdout.strip() if capture else ""


@dataclass
class Results:
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def run(self, label, action):
        print(f"\n── {label} ──", flush=True)
        try:
            action()
        except Skipped as error:
            self.skipped.append(label)
            print(f"   {label}: {error}", flush=True)
        except (Failed, OSError) as error:
            self.failed.append(label)
            print(f"   {label}: FAILED ({error})", flush=True)
        else:
            print(f"   {label}: completed", flush=True)

    def summary(self):
        if self.skipped:
            print(f"\nskipped: {' '.join(self.skipped)}")
        if self.failed:
            print(
                f"\nfailed: {' '.join(self.failed)} — rerun daily-update when convenient."
            )
        return 1 if self.failed else 2 if self.skipped else 0
