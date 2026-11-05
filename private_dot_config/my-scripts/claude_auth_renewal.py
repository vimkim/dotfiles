"""Cache Claude renewal reminders without running Claude or storing secrets."""

import datetime as dt
import fcntl
import json
import math
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time

DAY = 86400
WINDOW_DAYS = 3  # Claude Code 2.1.318: chunk-gdkqhwa0.js and chunk-gvr4gxa7.js.
WARN_DAYS = 7


def read_json(path):
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("expected an object")
    return data


def text(value):
    return "".join(c for c in str(value) if c.isprintable())[:160]


def config_dirs(home):
    directories = {home / ".claude"}
    directories.update(p.parent for p in home.glob(".claude*/.credentials.json"))
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        directories.add(Path(os.environ["CLAUDE_CONFIG_DIR"]).expanduser())
    return sorted({p.resolve() for p in directories})


def login_notice(config, home, now):
    command = "claude auth login"
    if config != (home / ".claude").resolve():
        command = f"CLAUDE_CONFIG_DIR={shlex.quote(text(config))} {command}"
    label = text(config)
    try:
        metadata = home / ".claude.json" if config == (home / ".claude").resolve() else config / ".claude.json"
        try:
            email = read_json(metadata).get("oauthAccount", {}).get("emailAddress")
            if email:
                label = f"{text(email)} ({label})"
        except (OSError, ValueError, AttributeError):
            pass
        oauth = read_json(config / ".credentials.json").get("claudeAiOauth", {})
        latest = oauth.get("refreshTokenExpiresAt")
        if not oauth.get("refreshToken"):
            return f"Claude: {label}: no stored renewable sign-in; run {command}"
        if (isinstance(latest, bool) or not isinstance(latest, (int, float))
                or not math.isfinite(latest) or not 1735689600000 <= latest <= (now + 3650 * DAY) * 1000):
            return f"Claude: {label}: renewal date unknown; check claude auth status, then {command}"
        latest /= 1000
        access_expiry = oauth.get("expiresAt")
        if isinstance(access_expiry, (int, float)) and access_expiry / 1000 > latest + WINDOW_DAYS * DAY:
            return f"Claude: {label}: conflicting expiry metadata; check claude auth status"
        earliest = latest - WINDOW_DAYS * DAY
        if earliest - now > WARN_DAYS * DAY:
            return None
        start, end = (dt.datetime.fromtimestamp(t, dt.timezone.utc).date() for t in (earliest, latest))
        state = "may have expired" if now >= latest else "can expire now" if now >= earliest else "expires"
        action = "renew now" if now >= earliest else f"renew before {start}"
        return f"Claude: {label}: {state} {start}–{end} UTC; {action}: {command}"
    except FileNotFoundError:
        if config.exists():
            return f"Claude: {label}: no stored sign-in; run {command}"
    except (OSError, ValueError, AttributeError, OverflowError):
        return f"Claude: {label}: cannot read renewal metadata; check claude auth status"
    return None


def token_notices(directory, now):
    today = dt.datetime.fromtimestamp(now, dt.timezone.utc).date()
    for path in sorted(directory.glob("*.json")):
        if not path.stem.isdigit():
            continue
        command = f"claude-account add {int(path.stem)}"
        try:
            account = read_json(path)
            label = text(account.get("label") or f"slot {path.stem}")
            # Pasted tokens may predate `added`; this is an estimate, not a server expiry.
            expires = dt.date.fromisoformat(account["added"]) + dt.timedelta(days=365)
            if (expires - today).days > 30:
                continue
            yield f"Claude: ai{int(path.stem)} ({label}): setup-token estimated expiry {expires} UTC; renew with {command}"
        except (OSError, ValueError, KeyError, TypeError):
            yield f"Claude: ai{int(path.stem)}: token expiry unknown; check claude-account list; renew with {command}"


def refresh(force=False):
    home = Path.home()
    directory = Path(os.environ.get("XDG_CACHE_HOME") or home / ".cache") / "claude-auth-renewal"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "refresh.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        now = time.time()
        notice = directory / "notice"
        if not force and notice.exists() and now - notice.stat().st_mtime < 3600:
            return
        messages = [message for config in config_dirs(home)
                    if (message := login_notice(config, home, now))]
        state = Path(os.environ.get("XDG_STATE_HOME") or home / ".local/state")
        accounts = Path(os.environ.get("CLAUDE_ACCOUNTS_DIR") or state / "claude-accounts")
        messages.extend(token_notices(accounts, now))
        descriptor, temporary = tempfile.mkstemp(prefix=".notice-", dir=directory)
        try:
            with os.fdopen(descriptor, "w") as handle:
                handle.write("\n".join([str(int(now)), *messages]) + "\n")
            os.replace(temporary, notice)
        finally:
            Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    refresh(force="--force" in sys.argv[1:])
