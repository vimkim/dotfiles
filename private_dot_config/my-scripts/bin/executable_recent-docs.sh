#!/usr/bin/env bash
# List all regular .html/.md files, newest first. Usage: recent-docs.sh [directory ...]
# With no directories, search the caller's working directory. Requires Python 3.9+.
# Prefer fd; otherwise use find, pruning hidden entries and node_modules.
# The dependency-free fallback reads ancestor/nested .gitignore, .ignore and
# .fdignore files, with globs, anchored paths, **, escapes and ! negations.
# It does not read Git configuration/info/exclude or fd's global ignore file;
# Extended brace globs and POSIX named character classes require native fd parsing.
set -euo pipefail

exec python3 - "$@" <<'PY'
import datetime
import fnmatch
import os
import re
import shutil
import stat
import subprocess
import sys


def glob_regex(pattern):
    """Translate path globs; * and ? cannot cross a directory separator."""
    result = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        index += 1
        if char == "\\":
            if index == len(pattern):
                return r"(?!)"  # A trailing escape cannot match anything.
            result.append(re.escape(pattern[index]))
            index += 1
        elif char == "*":
            end = index
            while end < len(pattern) and pattern[end] == "*":
                end += 1
            if end > index and (index == 1 or pattern[index - 2] == "/"):
                if end == len(pattern):
                    result.append(".*")
                elif pattern[end] == "/":
                    result.append("(?:[^/]+/)*")
                    end += 1
                else:
                    result.append("[^/]*")
            else:
                result.append("[^/]*")
            index = end
        elif char == "?":
            result.append("[^/]")
        elif char == "[":
            end = index + (index < len(pattern) and pattern[index] in "!^")
            if end < len(pattern) and pattern[end] == "]":
                end += 1
            end = pattern.find("]", end)
            if end < 0:
                result.append(r"\[")
            else:
                # Git/fd accept both ! and ^ to negate a bracket class.
                bracket = pattern[index - 1:end + 1]
                if bracket.startswith("[^"):
                    bracket = "[!" + bracket[2:]
                result.append("(?!/)" + fnmatch.translate(bracket))
                # Its end anchor applies only to the class, so remove it.
                result[-1] = result[-1].removesuffix(r"\Z").removesuffix(r"\z")
                index = end + 1
        else:
            result.append(re.escape(char))
    return "".join(result)


def read_rules(directory, name):
    try:
        with open(os.path.join(directory, name), errors="surrogateescape") as source:
            lines = source.read().splitlines()
    except FileNotFoundError:
        return ()
    rules = []
    for line in lines:
        # Strip only unescaped trailing spaces.
        while line.endswith(" "):
            preceding = line[:-1]
            escapes = len(preceding) - len(preceding.rstrip("\\"))
            if escapes % 2:
                break
            line = preceding
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        directory_only = line.endswith("/")
        if directory_only:
            line = line[:-1]
        anchored = "/" in line
        line = line.removeprefix("/")
        if not line:
            continue
        if re.search(r"(?<!\\)(?:\[\[:[a-z]+:\]\]|[{}])", line):
            raise ValueError(f"extended ignore patterns require fd: {os.path.join(directory, name)}")
        prefix = "" if anchored else "(?:.*/)?"
        rules.append((directory, re.compile(prefix + glob_regex(line), re.DOTALL),
                      directory_only, negated))
    return tuple(rules)


def ignored(path, is_directory, groups):
    # fd-specific files take precedence over .ignore, then .gitignore,
    # even when the lower-priority file is deeper in the tree.
    for rules in reversed(groups):
        for base, regex, directory_only, negated in reversed(rules):
            if directory_only and not is_directory:
                continue
            relative = os.path.relpath(path, base)
            if regex.fullmatch(relative):
                return not negated
    return False


class FindIgnores:
    def __init__(self, roots):
        self.roots = set(roots)
        self.cache = {}

    def context(self, directory):
        if directory in self.cache:
            return self.cache[directory]
        parent = os.path.dirname(directory)
        groups, blocked = self.context(parent) if parent != directory else (((), (), ()), False)
        if directory in self.roots:
            blocked = False  # Explicit search roots are always traversed, as with fd.
        elif not blocked:
            blocked = ignored(directory, True, groups)
        groups = tuple(previous + read_rules(directory, name) for previous, name in zip(
            groups, (".gitignore", ".ignore", ".fdignore")))
        self.cache[directory] = groups, blocked
        return groups, blocked

    def allows(self, path):
        groups, blocked = self.context(os.path.dirname(path))
        return not blocked and not ignored(path, False, groups)


def candidates(stream, ignores):
    pending = b""
    while chunk := stream.read(65536):
        records = (pending + chunk).split(b"\0")
        pending = records.pop()
        for path in records:
            if ignores is not None and not ignores.allows(os.fsdecode(path)):
                continue
            try:
                metadata = os.stat(path, follow_symlinks=False)
                if stat.S_ISREG(metadata.st_mode):
                    yield metadata.st_mtime_ns, path
            except FileNotFoundError:
                continue  # A file can disappear while the search is running.
            except OSError as error:
                print(f"Warning: {error}", file=sys.stderr)


def main():
    roots = [os.path.abspath(path) for path in (sys.argv[1:] or [os.getcwd()])]
    for root in roots:
        if not os.path.isdir(root):
            print(f"recent-docs.sh: not a directory: {root}", file=sys.stderr)
            return 1
    ignores = None
    if shutil.which("fd"):
        command = ["fd", "--no-require-git", "--ignore-case", "--type", "f",
                   "--exclude", "node_modules", "--extension", "html", "--extension", "md",
                   "--print0", "--color", "never", ".", *roots]
    else:
        print("Warning: fd is not installed; using find instead.", file=sys.stderr)
        ignores = FindIgnores(roots)
        command = ["find", "-H", *roots, "-mindepth", "1", "(", "-type", "d", "(",
                   "-name", ".*", "-o", "-name", "node_modules", ")", "-prune", ")",
                   "-o", "(", "-type", "f", "!", "-name", ".*", "(", "-iname", "*.html",
                   "-o", "-iname", "*.md", ")", "-print0", ")"]
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        newest = sorted(candidates(process.stdout, ignores), reverse=True)
        status = process.wait()
    if status:
        return status if status > 0 else 128 - status
    for modified_ns, path in newest:
        modified = datetime.datetime.fromtimestamp(modified_ns // 1_000_000_000)
        name = os.fsdecode(path).replace("\\", "\\\\").replace("\n", r"\n").replace("\r", r"\r").replace("\t", r"\t")
        print(f"{modified:%Y-%m-%d %H:%M}  {name}")
    return 0


try:
    sys.exit(main())
except (OSError, ValueError) as error:
    print(f"recent-docs.sh: {error}", file=sys.stderr)
    sys.exit(1)
PY
