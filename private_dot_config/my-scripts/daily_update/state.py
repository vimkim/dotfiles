"""Daily stamps and offline startup/status output."""

import os
import time
from datetime import date
from pathlib import Path

from . import skills
from .tools import resolve


class State:
    def __init__(self):
        cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        self.stamp = cache / "daily-update.stamp"
        self.directory = cache / "daily-update"
        self.stale_cache = self.directory / "stale.tsv"
        self.today = date.today().isoformat()

    def stamped_day(self):
        try:
            return self.stamp.read_text().strip()
        except OSError:
            return ""

    def pending(self):
        return self.stamped_day() != self.today

    def mark(self):
        skills.write_atomic(self.stamp, self.today + "\n")

    def cache_stale(self, rows):
        skills.write_atomic(
            self.stale_cache, "".join(f"{n}\t{r}\n" for n, r in rows.items())
        )

    def rows(self):
        # Only filesystem probes: shell startup must remain offline.
        current = Path.home() / ".codex/packages/standalone/current"
        if current.exists():
            version = current.resolve().name.split("-")[0]
            staged = current.parent / "auto-update-version"
            try:
                next_version = staged.read_text().strip().split("-")[0]
            except OSError:
                next_version = ""
            suffix = (
                f"  →  {next_version} staged"
                if next_version and next_version != version
                else ""
            )
            yield f"codex    {version}{suffix}"
        claude = resolve("claude")
        if claude and Path(claude).resolve().name[:1].isdigit():
            yield f"claude   {Path(claude).resolve().name}"
        try:
            days = int((time.time() - skills.lock_path().stat().st_mtime) // 86400)
            yield (
                "skills   synced today"
                if days == 0
                else f"skills   synced {days} day{'s' if days != 1 else ''} ago"
            )
        except OSError:
            pass
        try:
            names = [
                line.split("\t")[0]
                for line in self.stale_cache.read_text().splitlines()
                if line
            ]
        except OSError:
            names = []
        if names:
            suffix = f", and {len(names) - 8} more" if len(names) > 8 else ""
            yield f"stale    {', '.join(names[:8])}{suffix}"
            yield "         delete with daily-update --prune"

    def status(self):
        pending = self.pending()
        title = "pending" if pending else f"done {self.stamped_day()}"
        print(f"\n┌─ daily upkeep {title} ──────────────────────")
        for row in self.rows():
            print(f"│  {row}")
        tail = (
            "run daily-update to upgrade and silence this for today"
            if pending
            else "next reminder: tomorrow"
        )
        print(f"└─ {tail}\n")
