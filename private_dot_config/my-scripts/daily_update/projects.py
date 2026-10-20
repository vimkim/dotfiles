"""TOML inventory, checkout refresh and project-owned sync recipes."""

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .common import Failed, Skipped, checked, command


@dataclass(frozen=True)
class Project:
    name: str
    path: Path
    github: str
    kind: str = "tool"
    primary_main: bool = False

    @property
    def label(self):
        return f"{self.kind}:{self.name}"


def default_config():
    return (
        Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        / "my-scripts/daily-update.toml"
    )


def load_projects(path):
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    if set(data) != {"projects"} or not isinstance(data["projects"], list):
        raise ValueError("expected a projects array of tables")
    projects = []
    names, paths = set(), set()
    for item in data["projects"]:
        if not isinstance(item, dict) or set(item) - {
            "name",
            "path",
            "github",
            "kind",
            "primary_main",
        }:
            raise ValueError("invalid project fields")
        for key in ("name", "path", "github"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"project requires a nonempty {key}")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", item["name"]):
            raise ValueError("invalid project name")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", item["github"]):
            raise ValueError("github must be owner/repository")
        path = Path(item["path"]).expanduser()
        if not path.is_absolute():
            raise ValueError("project paths must be absolute or start with ~/")
        kind = item.get("kind", "tool")
        primary = item.get("primary_main", False)
        if kind not in ("tool", "collection") or not isinstance(primary, bool):
            raise ValueError(
                "kind must be tool/collection and primary_main must be boolean"
            )
        if item["name"] in names or path.resolve() in paths:
            raise ValueError("duplicate project name or path")
        names.add(item["name"])
        paths.add(path.resolve())
        projects.append(Project(item["name"], path, item["github"], kind, primary))
    return projects


def expected_origin(url, github):
    return url in {
        f"https://github.com/{github}",
        f"https://github.com/{github}.git",
        f"git@github.com:{github}",
        f"git@github.com:{github}.git",
    }


def git(repo, *args):
    return command("git", "-C", repo, *args)


def refresh(repo, *, github=None, primary_main=False, dotfiles=False):
    missing = (
        "missing independent source checkout"
        if dotfiles
        else "missing independent checkout"
    )
    if not repo.is_dir():
        raise Skipped(f"skipped ({missing})")
    root = git(repo, "rev-parse", "--show-toplevel")
    if root.returncode or Path(root.stdout.strip()) != repo.resolve():
        raise Skipped(f"skipped ({missing})")
    status = git(repo, "status", "--porcelain", "--untracked-files=all")
    if status.returncode:
        raise Failed("cannot inspect checkout")
    if status.stdout:
        raise Skipped("skipped (dirty checkout)")
    branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    upstream = git(repo, "rev-parse", "--abbrev-ref", "@{upstream}")
    if branch.returncode or upstream.returncode:
        reason = (
            "requires main tracking origin/main"
            if dotfiles
            else "detached HEAD or no upstream"
        )
        raise Skipped(f"skipped ({reason})")
    branch, upstream = branch.stdout.strip(), upstream.stdout.strip()
    if primary_main:
        if (
            branch != "main"
            or upstream != "origin/main"
            or (not dotfiles and (repo.is_symlink() or not (repo / ".git").is_dir()))
        ):
            guard = (
                "main tracking origin/main"
                if dotfiles
                else "primary main tracking origin/main"
            )
            raise Skipped(f"skipped (requires {guard})")
        origin = git(repo, "config", "--get", "remote.origin.url")
        if origin.returncode or not expected_origin(origin.stdout.strip(), github):
            raise Skipped("skipped (unexpected origin)")
    remote = git(repo, "config", "--get", f"branch.{branch}.remote")
    remote = remote.stdout.strip() if not remote.returncode else ""
    if not remote or remote == ".":
        raise Skipped("skipped (no published upstream)")
    fetch = [remote]
    if primary_main:
        # An absent remote main must fail instead of authorizing stale code.
        fetch.append("refs/heads/main:refs/remotes/origin/main")
    checked("git", "-C", repo, "fetch", "--", *fetch, reason="fetch", capture=False)
    ancestor = git(repo, "merge-base", "--is-ancestor", "HEAD", upstream)
    if ancestor.returncode == 1:
        raise Skipped("skipped (ahead or diverged checkout)")
    if ancestor.returncode:
        raise Failed("cannot compare checkout with upstream")
    checked(
        "git",
        "-C",
        repo,
        "merge",
        "--ff-only",
        "--",
        upstream,
        reason="fast-forward",
        capture=False,
    )


def sync(project):
    refresh(project.path, github=project.github, primary_main=project.primary_main)
    if not (project.path / "justfile").is_file():
        raise Failed("missing local justfile")
    result = command(
        "just", "--justfile", "./justfile", "sync", cwd=project.path, capture=False
    )
    if result.returncode == 2:
        raise Skipped("partial/skipped (sync exit 2)")
    if result.returncode:
        raise Failed(f"sync exit {result.returncode}")


def run_projects(projects, results):
    ordered = list(projects)
    if os.environ.get("DAILY_UPDATE_COLLECTION_ORDER") == "cubrid-first":
        slots = [i for i, p in enumerate(ordered) if p.kind == "collection"]
        for i, project in zip(slots, reversed([ordered[i] for i in slots])):
            ordered[i] = project
    for project in ordered:
        results.run(project.label, lambda project=project: sync(project))
