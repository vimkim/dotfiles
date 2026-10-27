"""Command routing and feature orchestration."""

import argparse
import sys
from pathlib import Path

from . import dotfiles, github, projects, skills, tools
from .common import Failed, Results
from .state import State


def parser():
    cli = argparse.ArgumentParser(
        description="Daily dotfiles, tool and skill upkeep (Python 3.11+)."
    )
    cli.add_argument(
        "--config",
        type=Path,
        default=projects.default_config(),
        help="personal-project TOML file",
    )
    mode = cli.add_mutually_exclusive_group()
    for flag, help_text in (
        ("run", "run all upkeep and stamp today (default)"),
        ("dotfiles-only", "fetch, fast-forward and apply dotfiles without stamping today"),
        ("remind", "print pending upkeep, or stay silent if run today"),
        ("status", "show cached versions and today's run state"),
        ("stale", "list lock-backed stale third-party skills"),
        ("prune", "move stale third-party skills into recoverable trash"),
        ("reset", "clear today's stamp"),
    ):
        mode.add_argument(f"--{flag}", action="store_true", help=help_text)
    return cli


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["help"]:
        argv = ["--help"]
    args = parser().parse_args(argv)
    state = State()
    try:
        if args.remind:
            if state.pending():
                state.status()
            return 0
        if args.status:
            state.status()
            return 0
        if args.reset:
            state.stamp.unlink(missing_ok=True)
            print(
                "daily-update: stamp cleared; the reminder returns on the next shell."
            )
            return 0
        if args.dotfiles_only:
            results = Results()
            results.run("dotfiles", dotfiles.update)
            return results.summary()
        # Validate the full inventory before any update or prune can mutate state.
        try:
            configured = projects.load_projects(args.config.expanduser())
        except (OSError, ValueError) as error:
            raise Failed(f"invalid project config {args.config}: {error}") from error
        if args.stale:
            rows = skills.stale(configured)
            state.cache_stale(rows)
            skills.report(rows)
            return 0
        if args.prune:
            skills.prune(configured, state)
            return 0
        results = Results()
        results.run("dotfiles", dotfiles.update)
        results.run("gh", github.cli)
        results.run("gh-stack", github.stack)
        for agent in ("codex", "claude-code"):
            results.run(f"gh-stack skill:{agent}", lambda agent=agent: github.skill(agent))
        results.run("codex", tools.codex)
        results.run("claude", lambda: tools.upgrade("claude", "update"))
        projects.run_projects(configured, results)
        results.run("skills", lambda: skills.update(configured))

        def scan():
            rows = skills.stale(configured)
            state.cache_stale(rows)
            skills.report(rows)

        results.run("stale scan", scan)
        state.mark()
        code = results.summary()
        print(f"stamped {state.today}; the startup reminder is silent until tomorrow.")
        return code
    except (Failed, OSError) as error:
        print(f"daily-update: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ndaily-update: interrupted", file=sys.stderr)
        return 130
