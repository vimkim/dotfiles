"""Lock-backed third-party updates and recoverable stale-skill pruning."""

import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from .common import Failed, command
from .tools import upgrade

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def lock_path():
    return Path.home() / ".agents/.skill-lock.json"


def store_path():
    return Path.home() / ".agents/skills"


def claude_skills():
    return (
        Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "skills"
    )


def personal_names(projects):
    names = set()

    def fail(error):
        raise error

    for project in projects:
        if project.kind != "collection" or not project.path.exists():
            continue
        for root, dirs, files in os.walk(project.path, onerror=fail):
            depth = len(Path(root).relative_to(project.path).parts)
            if depth >= 2:
                dirs[:] = []
            if "SKILL.md" in files:
                names.add(Path(root).name.casefold())
    return names


def personal_source(source, projects):
    for project in projects:
        if project.kind != "collection":
            continue
        if source == str(project.path):
            return True
        pattern = rf"(?:https://github\.com/|git@github\.com:)?{re.escape(project.github)}(?:\.git)?(?:/.*)?"
        if re.fullmatch(pattern, source, re.IGNORECASE):
            return True
    return False


def inventory(projects):
    path = lock_path()
    if not path.exists():
        return {}, []
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or not isinstance(data.get("skills"), dict):
            raise ValueError("invalid skills lock")
        entries = data["skills"]
        for name, entry in entries.items():
            if (
                not NAME.fullmatch(name)
                or not isinstance(entry, dict)
                or not isinstance(entry.get("source"), str)
                or not isinstance(entry.get("sourceUrl", ""), str)
            ):
                raise ValueError("invalid skills lock entry")
        protected = personal_names(projects)
        eligible = [
            name
            for name, entry in entries.items()
            # gh-stack is reconciled explicitly through gh skill for each agent.
            if name.casefold() != "gh-stack"
            and name.casefold() not in protected
            and not personal_source(entry["source"], projects)
            and not personal_source(entry.get("sourceUrl", ""), projects)
        ]
        return data, eligible
    except (OSError, ValueError) as error:
        raise Failed(f"invalid lock/source evidence: {error}") from error


def update(projects):
    _, eligible = inventory(projects)
    if eligible:
        upgrade(
            "npx", "--yes", "skills@1.7.0", "update", *eligible, "--global", "--yes"
        )
    else:
        print("   skills: no third-party updates to check")


def stale(projects):
    data, eligible = inventory(projects)
    entries = data.get("skills", {})
    reasons = {}
    if shutil.which("gh"):
        sources = sorted(
            {
                entries[n]["source"]
                for n in eligible
                if entries[n].get("sourceType") == "github"
            }
        )
        for source in sources:
            result = command(
                "gh",
                "api",
                f"repos/{source}/git/trees/HEAD?recursive=1",
                "--jq",
                '.tree[] | select(.path|endswith("/SKILL.md")) | .path | split("/")[-2]',
            )
            upstream = set(result.stdout.splitlines())
            # API failures or unexpected output cannot authorize removal.
            if (
                result.returncode
                or not upstream
                or not all(NAME.fullmatch(n) for n in upstream)
            ):
                continue
            for name in eligible:
                if (
                    entries[name]["source"] == source
                    and name not in upstream
                    and (store_path() / name).is_dir()
                ):
                    reasons[name] = f"deleted from {source} upstream"
    for name in eligible:
        if not (store_path() / name).is_dir():
            reasons.setdefault(name, "lock entry, no installed directory")
        link = claude_skills() / name
        if link.is_symlink() and not link.exists():
            reasons.setdefault(name, "broken symlink in ~/.claude/skills")
    return reasons


def report(rows):
    print("\n── stale skills ──")
    if not rows:
        print("   none")
    for name, reason in rows.items():
        print(f"   {name}  ({reason})")
    if rows:
        print(f"\n   {len(rows)} of these can be deleted with daily-update --prune")


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prune(projects, state):
    rows = stale(projects)
    if not rows:
        write_atomic(state.stale_cache, "")
        print("No stale skills to prune.")
        return
    state.directory.mkdir(parents=True, exist_ok=True)
    trash_root = state.directory / "trash"
    trash_root.mkdir(exist_ok=True)
    trash = Path(
        tempfile.mkdtemp(
            prefix=datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=trash_root
        )
    )
    shutil.copy2(lock_path(), trash / ".skill-lock.json.bak")
    data = json.loads(lock_path().read_text())
    for name, reason in rows.items():
        installed = store_path() / name
        if installed.is_dir() and not installed.is_symlink():
            shutil.move(str(installed), trash / name)
        link = claude_skills() / name
        if link.is_symlink():
            link.unlink()
        data["skills"].pop(name, None)
        write_atomic(lock_path(), json.dumps(data, indent=2) + "\n")
        print(f"   removed {name} ({reason})")
    write_atomic(state.stale_cache, "")
    print(f"\npruned {len(rows)} skill(s); recoverable copies kept in {trash}")
