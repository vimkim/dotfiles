#!/usr/bin/env python3
"""git-log-pick (glp) — pick two commits from the `git log --all` map with fzf,
then print `git-log.py <A> <B>` with the picks marked "◀ A" / "◀ B".

Each pick is a point in history, not a branch name: the final log shows only
what is reachable backward from A and from B. Type a branch name in fzf to
jump to its tip, or move the cursor to any older commit to start from there.

Usage:
  glp                  # pick A, then pick B
  glp A                # A given, pick B
  glp A B              # no picking, straight to the log
  glp -n30 --since=1.month
                       # arguments starting with '-' go to git-log.py
  glp --all-branch     # label every ref, not just those at A and B

In the picker: the cursor starts on HEAD, so Enter alone picks HEAD.
Enter confirms, Esc aborts, ctrl-/ toggles the commit preview.
Lines with only graph edges (no commit) are not selectable; the picker reopens.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
HASH = re.compile(r"\b[0-9a-f]{7,40}\b")
HERE = Path(__file__).resolve().parent

# The preview calls this script back with the line (fzf quotes {} itself).
# No shell pipeline here: fzf would expand regex braces like {7,40} as field
# placeholders. $SHELL is still pinned to sh so nushell/fish never parse it.
PREVIEW = f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} --preview-line {{}}"


def graph() -> bytes:
    return subprocess.run(
        ["git", "log", "--graph", "--oneline", "--decorate", "--all", "--color=always"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def head_position(lines: bytes) -> int | None:
    """1-based index of the graph line for HEAD, or None (e.g. unborn HEAD)."""
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
        stdout=subprocess.PIPE,
        text=True,
    )
    head = proc.stdout.strip()
    if not head:
        return None
    for i, line in enumerate(lines.decode(errors="replace").splitlines(), 1):
        match = HASH.search(ANSI.sub("", line))
        if match and head.startswith(match.group(0)):
            return i
    return None


def pick(prompt: str, header: str) -> str | None:
    """Return the selected commit hash, or None if the user aborted.

    The cursor starts on HEAD, so Enter alone picks it.
    """
    lines = graph()
    pos = head_position(lines)
    while True:
        proc = subprocess.run(
            [
                "fzf", "--ansi", "--no-sort", "--reverse", "--height=80%",
                f"--prompt={prompt} > ",
                f"--header={header}",
                f"--preview={PREVIEW}",
                "--preview-window=right,50%,wrap",
                "--bind=ctrl-/:toggle-preview",
                *([f"--bind=load:pos({pos})"] if pos else []),
            ],
            input=lines,
            stdout=subprocess.PIPE,
            env={**os.environ, "SHELL": "/bin/sh"},
        )
        if proc.returncode != 0:  # Esc / ctrl-c / no match
            return None
        match = HASH.search(ANSI.sub("", proc.stdout.decode(errors="replace")))
        if match:
            return match.group(0)


def preview(line: str) -> int:
    match = HASH.search(ANSI.sub("", line))
    if not match:
        return 0  # graph-only line: empty preview
    return subprocess.run(
        ["git", "show", "--color=always", "--stat", "-p", match.group(0)]
    ).returncode


def main(argv: list[str]) -> int:
    if argv[:1] == ["--preview-line"]:
        return preview(" ".join(argv[1:]))
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__.strip())
        return 0

    opts = [a for a in argv if a.startswith("-")]
    revs = [a for a in argv if not a.startswith("-")]
    if len(revs) > 2:
        sys.exit("git-log-pick: at most two revisions")

    if subprocess.run(
        ["git", "rev-parse", "--git-dir"], stdout=subprocess.DEVNULL
    ).returncode != 0:
        return 128

    if not revs:
        a = pick("A", "pick the first starting point   [ctrl-/ preview]")
        if a is None:
            return 130
        revs.append(a)
    if len(revs) == 1:
        b = pick("B", f"A = {revs[0]} — pick the second starting point   [ctrl-/ preview]")
        if b is None:
            return 130
        revs.append(b)

    log = str(HERE / "git-log.py")
    cmd = [log, *opts, f"--mark=A={revs[0]}", f"--mark=B={revs[1]}", *revs]
    os.execv(sys.executable, [sys.executable, *cmd])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
