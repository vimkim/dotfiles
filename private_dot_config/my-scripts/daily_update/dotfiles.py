"""Configured dotfiles source refresh and conservative deployment."""

import shutil
from pathlib import Path

from .common import Failed, Skipped, checked, command
from .projects import refresh


def update():
    if not all(
        shutil.which(tool) for tool in ("chezmoi", "git", "chezmoi-apply-unmodified")
    ):
        raise Skipped("skipped (requires chezmoi, git and chezmoi-apply-unmodified)")
    source = checked("chezmoi", "source-path", reason="cannot locate configured source")
    repo = Path(source)
    if not repo.is_absolute():
        raise Skipped("skipped (missing independent source checkout)")
    refresh(repo, github="vimkim/dotfiles", primary_main=True, dotfiles=True)
    result = command("chezmoi-apply-unmodified", "--source", repo)
    output = result.stdout + result.stderr
    if output:
        print(output.rstrip(), flush=True)
    if result.returncode:
        raise Failed(f"apply exit {result.returncode}")
    if any(
        line.startswith(
            (
                "Skipped locally changed target: ",
                "Skipped pre-existing target without last-write state: ",
            )
        )
        for line in output.splitlines()
    ):
        raise Skipped("partial/skipped (preserved local targets)")
