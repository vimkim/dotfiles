"""GitHub CLI, gh-stack and its user-scoped agent skills."""

import shutil
from pathlib import Path

from .common import Failed, Results, Skipped, checked, command
from .tools import resolve


def cli(*, install=False):
    binary = resolve("gh")
    brew = shutil.which("brew")
    if not binary:
        if not brew:
            raise Skipped("install Homebrew first, then retry chezmoi apply")
        checked(
            brew, "install", "gh", reason="GitHub CLI installation failed", capture=False
        )
        return
    if install and not command(binary, "skill", "install", "--help").returncode:
        return
    if brew:
        prefix = checked(brew, "--prefix", reason="cannot inspect Homebrew prefix")
        if prefix and Path(binary).resolve().is_relative_to(prefix):
            installed = command(brew, "list", "--formula", "--versions", "gh")
            if not installed.returncode and installed.stdout.strip():
                checked(
                    brew, "upgrade", "gh", reason="GitHub CLI upgrade failed", capture=False
                )
                return
    raise Skipped(
        f"{binary} is not Homebrew-managed; update it with its package manager"
    )


def gh(*args, capture=False):
    binary = resolve("gh")
    if not binary:
        raise Skipped("gh not installed")
    return checked(binary, *args, reason=f"gh {' '.join(args)} failed", capture=capture)


def stack(*, install=False):
    extensions = gh("extension", "list", capture=True)
    for line in extensions.splitlines():
        fields = line.split()
        if fields[:2] == ["gh", "stack"]:
            if len(fields) < 3 or fields[2].casefold() != "github/gh-stack":
                raise Failed("existing gh stack comes from another source; preserved")
            if not install:
                gh("extension", "upgrade", "gh-stack")
            return
    gh("extension", "install", "github/gh-stack")


def skill(agent):
    # Explicit placement also repairs missing installs. --force lets daily runs
    # replace the previous release without an interactive overwrite prompt.
    gh(
        "skill", "install", "github/gh-stack", "gh-stack",
        "--agent", agent, "--scope", "user", "--force",
    )


def bootstrap():
    results = Results()
    results.run("gh", lambda: cli(install=True))
    results.run("gh-stack", lambda: stack(install=True))
    for agent in ("codex", "claude-code"):
        results.run(f"gh-stack skill:{agent}", lambda agent=agent: skill(agent))
    code = results.summary()
    if code:
        print("GitHub tools: correct the reported problem and retry chezmoi apply.")
    # A skip must leave chezmoi's run-once script eligible for retry, too.
    return 1 if code else 0
