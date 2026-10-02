#!/usr/bin/env python3
"""git-log (gl) — compact, colored `git log --graph`.

Usage:
  git-log.py [git-log-options] [revisions]

  Arguments starting with '-' are git-log options (write -n30, not -n 30);
  everything else is a revision.

  no revisions      log --all and label every ref
  revisions given   log only their history; label only their refs (a raw
                    commit gets the refs pointing exactly at it) plus HEAD
  --all-branch      label every ref
  --mark=NAME=REV   append "◀ NAME" to REV's line (repeatable; used by glp)

git-log.sh is a thin wrapper around this script.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

PRETTY = (
    "%C(auto)%h %C(magenta)%as%C(reset) %C(blue)%an%C(reset)%C(auto)%d %s"
    " %C(black)%C(bold)%cr%C(reset)"
)
DEFAULT_OPTS = ["--graph", "--oneline", "--color", "--decorate", "--date-order"]
PAGER = "less -iRFSX"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
HASH = re.compile(r"\b[0-9a-f]{7,40}\b")
MARK = "\x1b[1;33m"
RESET = "\x1b[m"


def git_out(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    )
    return proc.stdout if proc.returncode == 0 else ""


def commit_of(rev: str) -> str:
    return git_out("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip()


def refs_for(rev: str) -> list[str]:
    """Full ref names to label for one revision argument."""
    refs = [
        line.lstrip("^")
        for line in git_out("rev-parse", "--symbolic-full-name", rev).splitlines()
        if line.lstrip("^").startswith("refs/")
    ]
    if not refs:
        commit = commit_of(rev)
        if commit:
            refs = git_out(
                "for-each-ref", f"--points-at={commit}", "--format=%(refname)"
            ).split()
    return refs


def decorate_opts(revs: list[str]) -> list[str]:
    # HEAD keeps the filter non-empty: no --decorate-refs at all labels everything.
    refs = ["HEAD"]
    for rev in revs:
        refs += [r for r in refs_for(rev) if r not in refs]
    return [f"--decorate-refs={r}" for r in refs]


def marked(line: str, marks: dict[str, list[str]]) -> str:
    match = HASH.search(ANSI.sub("", line))
    if not match:
        return line
    for commit, names in marks.items():
        if commit.startswith(match.group(0)):
            end = "\n" if line.endswith("\n") else ""
            return f"{line.rstrip(chr(10))} {MARK}◀ {' '.join(names)}{RESET}{end}"
    return line


def run_marked(cmd: list[str], marks: dict[str, list[str]]) -> int:
    """Stream git log through the marker into less (or stdout when piped)."""
    git = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, errors="replace")
    pager = None
    out = sys.stdout
    if sys.stdout.isatty():
        pager = subprocess.Popen(
            PAGER.split(), stdin=subprocess.PIPE, text=True, errors="replace"
        )
        out = pager.stdin
    try:
        for line in git.stdout:
            out.write(marked(line, marks))
        if pager:
            pager.stdin.close()
    except BrokenPipeError:  # pager quit early
        git.terminate()
    if pager:
        pager.wait()
    elif out is sys.stdout:
        out.flush()
    return git.wait()


def main(argv: list[str]) -> int:
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__.strip())
        return 0

    opts: list[str] = []
    revs: list[str] = []
    all_labels = False
    mark_args: list[tuple[str, str]] = []
    for arg in argv:
        if arg == "--all-branch":
            all_labels = True
        elif arg.startswith("--mark="):
            name, _, rev = arg[len("--mark="):].partition("=")
            mark_args.append((name, rev))
        elif arg.startswith("-"):
            opts.append(arg)
        else:
            revs.append(arg)

    if not revs:
        revs = ["--all"]
    elif not all_labels:
        opts = decorate_opts(revs) + opts

    cmd = ["git", "log", *DEFAULT_OPTS, *opts, f"--pretty=format:{PRETTY}", *revs]

    marks: dict[str, list[str]] = {}
    for name, rev in mark_args:
        commit = commit_of(rev)
        if commit:
            marks.setdefault(commit, []).append(name)

    if not marks:
        os.execvpe("git", cmd, {**os.environ, "GIT_PAGER": PAGER})
    return run_marked(cmd, marks)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
