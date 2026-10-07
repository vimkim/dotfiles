#!/usr/bin/env python3
"""Pick an immediate child directory by modification time; print its absolute path."""

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional


@dataclass(frozen=True)
class DirectoryChoice:
    name: str
    path: str
    metadata: Optional[os.stat_result]
    link_target: str = ""


def directory_choices(root):
    """Parent first, then children newest first; equal timestamps sort by name.

    Hidden directories and symlinks to directories are included. Symlinks use
    the target directory's timestamp. Returned paths retain the link rather
    than resolving it. Files and dangling links are excluded.
    """
    entries = []
    with os.scandir(root) as directory:
        for entry in directory:
            try:
                if entry.is_dir():
                    entries.append(DirectoryChoice(
                        entry.name, entry.path, entry.stat(),
                        os.readlink(entry.path) if entry.is_symlink() else "",
                    ))
            except OSError:
                # Entries may disappear or become inaccessible during a scan.
                continue
    entries.sort(key=lambda choice: (-choice.metadata.st_mtime_ns, choice.name))
    try:
        parent_metadata = root.parent.stat()
    except OSError:
        parent_metadata = None
    return [DirectoryChoice("../", str(root.parent), parent_metadata), *entries]


def display_text(value):
    """Escape field separators and terminal controls without changing real paths."""
    escapes = {"\\": "\\\\", "\t": "\\t", "\n": "\\n", "\r": "\\r"}
    return "".join(
        escapes.get(char, char if char.isprintable() else f"\\u{ord(char):04x}")
        for char in value
    )


def display_size(size):
    value = size
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value}B" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024


def candidate_row(index, choice):
    if choice.metadata is None:
        metadata = "       -  -"
    else:
        modified = datetime.fromtimestamp(choice.metadata.st_mtime).strftime("%Y-%m-%d %H:%M")
        metadata = f"{display_size(choice.metadata.st_size):>8}  {modified}"
    metadata += "  \033[34m\uf07b\033[0m"
    name = "\033[34m" + display_text(choice.name) + "\033[0m"
    link = "\033[2m→ " + display_text(choice.link_target) + "\033[0m" if choice.link_target else ""
    return f"{index}\t{metadata}\t{name}\t{link}"


def pick_directory(choices, query=""):
    """fzf handles the terminal UI; stdout carries only the selected path."""
    fzf = shutil.which("fzf")
    if not fzf:
        print("dir-picker: fzf is required; install fzf and retry.", file=sys.stderr)
        return 127, None
    completed = subprocess.run(
        [fzf, "--read0", "--print0", "--no-multi", "--no-print-query", "--no-expect",
         "--sort", "--no-tac", "--height=60%", "--reverse",
         "--ansi", "--delimiter=\t", "--with-nth=2..", "--nth=2", "--accept-nth=1",
         "--no-exact", "--extended", "--smart-case", "--scheme=default",
         "--tiebreak=index",
         "--query=" + query,
         "--header=    Size  Modified          Name | Empty: newest first; query: relevance"],
        input=b"".join(os.fsencode(candidate_row(index, choice)) + b"\0"
                       for index, choice in enumerate(choices)),
        stdout=subprocess.PIPE,
    )
    if completed.returncode:
        return (128 - completed.returncode if completed.returncode < 0 else completed.returncode), None
    selected = os.fsdecode(completed.stdout.removesuffix(b"\0"))
    paths = {str(index): choice.path for index, choice in enumerate(choices)}
    if selected not in paths:
        print("dir-picker: fzf returned an invalid selection.", file=sys.stderr)
        return 2, None
    return 0, paths[selected]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default=".", help="directory to browse (default: current)")
    parser.add_argument("--list", action="store_true", help="list ordered paths without opening fzf")
    parser.add_argument("--query", default="", help="initial name search text (fzf extended syntax)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="emit a JSON string, or array with --list")
    output.add_argument("--null", action="store_true", help="terminate paths with NUL instead of newline")
    args = parser.parse_args()
    root = Path(os.path.abspath(os.path.expanduser(args.directory)))
    choices = directory_choices(root)
    if args.list:
        paths = [choice.path for choice in choices]
    else:
        status, selected = pick_directory(choices, args.query)
        if status:
            return status
        paths = [selected]
    if args.json:
        print(json.dumps(paths if args.list else paths[0]))
    else:
        separator = b"\0" if args.null else b"\n"
        sys.stdout.buffer.write(b"".join(os.fsencode(path) + separator for path in paths))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except OSError as error:
        print(f"dir-picker: {error}", file=sys.stderr)
        sys.exit(2)
