"""Consistent tool resolution and Codex/Claude upgrades."""

import os
import shutil
from pathlib import Path

from .common import Failed, Skipped, command


def resolve(name):
    local = Path.home() / ".local/bin" / name
    return (
        str(local)
        if local.is_file() and os.access(local, os.X_OK)
        else shutil.which(name)
    )


def upgrade(name, *args):
    binary = resolve(name)
    if not binary:
        raise Skipped(f"skipped ({name} not installed)")
    print(f"   {binary} {' '.join(args)}", flush=True)
    result = command(binary, *args, capture=False)
    if result.returncode:
        raise Failed(f"exit {result.returncode}")


def codex():
    binary = resolve("codex")
    brew = shutil.which("brew")
    if binary and brew:
        prefix = command(brew, "--prefix")
        if (
            not prefix.returncode
            and prefix.stdout.strip()
            and Path(binary).resolve().is_relative_to(prefix.stdout.strip())
        ):
            for kind in ("cask", "formula"):
                installed = command(brew, "list", f"--{kind}", "--versions", "codex")
                if not installed.returncode and installed.stdout.strip():
                    result = command(
                        brew, "upgrade", f"--{kind}", "codex", capture=False
                    )
                    if result.returncode:
                        raise Failed(f"exit {result.returncode}")
                    return
    upgrade("codex", "update")
