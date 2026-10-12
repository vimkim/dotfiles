#!/usr/bin/env python3
"""Local Codex prompt admission prototype; percentages refer to weekly quota."""

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

KOREA = ZoneInfo("Asia/Seoul")
CAP = 33
CAP_BY_DAY = {"2026-10-13": 66}  # Temporary exception, using Korean calendar days.
WARNING = 25
TIMEOUT = 15


class GuardError(Exception):
    pass


class GuardParser(argparse.ArgumentParser):
    def error(self, message):
        raise GuardError("Invalid daily hook arguments; check hooks.json")


class AppServer:
    """Metadata-only connection: never creates a thread or starts inference."""

    def __init__(self, binary, flags=()):
        self.binary = binary
        self.flags = flags
        self.request_id = 0

    async def __aenter__(self):
        self.process = await asyncio.create_subprocess_exec(
            self.binary, "app-server", "--stdio", *self.flags,
            "-c", "analytics.enabled=false",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return self

    async def __aexit__(self, *unused):
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

    async def send(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        await self.process.stdin.drain()

    async def request(self, method, params=None):
        self.request_id += 1
        identifier = self.request_id
        message = {"method": method, "id": identifier}
        if params is not None:
            message["params"] = params
        await self.send(message)
        while True:
            line = await self.process.stdout.readline()
            if not line:
                raise GuardError("Codex metadata connection closed")
            try:
                response = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise GuardError("Invalid Codex metadata response") from None
            if response.get("id") != identifier:
                continue
            if "error" in response:
                raise GuardError(f"Codex metadata request failed: {method}")
            return response.get("result", {})

    async def initialize(self):
        await self.request("initialize", {
            "clientInfo": {"name": "codex_daily_guard", "version": "0.1.0"}
        })
        await self.send({"method": "initialized", "params": {}})


def snapshot_from_metadata(account_result, limits, observed_at):
    account = account_result.get("account")
    if not isinstance(account, dict) or account.get("type") != "chatgpt":
        raise GuardError("This guard requires the default ChatGPT account")
    email = account.get("email")
    plan = account.get("planType")
    if not email or not plan or plan == "unknown":
        raise GuardError("Codex did not provide a stable account identity and plan")
    buckets = limits.get("rateLimitsByLimitId")
    bucket = buckets.get("codex") if isinstance(buckets, dict) else limits.get("rateLimits")
    if not isinstance(bucket, dict) or bucket.get("limitId") not in (None, "codex"):
        raise GuardError("Codex weekly quota bucket is unavailable")
    windows = [bucket.get(slot) for slot in ("primary", "secondary")]
    weekly = [w for w in windows if isinstance(w, dict) and w.get("windowDurationMins") == 10080]
    if len(weekly) != 1:
        raise GuardError("Codex weekly quota window is missing or ambiguous")
    snapshot = {
        "account_key": hashlib.sha256(email.lower().encode()).hexdigest(),
        "plan": plan,
        "used_percent": weekly[0].get("usedPercent"),
        "resets_at": weekly[0].get("resetsAt"),
        "observed_at": observed_at,
    }
    validate_snapshot(snapshot, observed_at)
    return snapshot


def validate_snapshot(snapshot, now):
    try:
        valid = (
            isinstance(snapshot["account_key"], str)
            and len(snapshot["account_key"]) == 64
            and all(c in "0123456789abcdef" for c in snapshot["account_key"])
            and isinstance(snapshot["plan"], str) and bool(snapshot["plan"])
            and type(snapshot["used_percent"]) is int
            and 0 <= snapshot["used_percent"] <= 100
            and type(snapshot["resets_at"]) is int and snapshot["resets_at"] > now
            and type(snapshot["observed_at"]) in (int, float)
            and now - 30 <= snapshot["observed_at"] <= now + 2
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise GuardError("Quota metadata is missing, invalid, or stale")


async def probe(binary, flags=()):
    async with AppServer(binary, flags) as server:
        async def read():
            await server.initialize()
            account = await server.request("account/read", {"refreshToken": False})
            limits = await server.request("account/rateLimits/read")
            return snapshot_from_metadata(account, limits, time.time())
        try:
            return await asyncio.wait_for(read(), TIMEOUT)
        except asyncio.TimeoutError:
            raise GuardError("Codex quota metadata timed out") from None


def day_at(timestamp):
    return datetime.fromtimestamp(timestamp, KOREA).date().isoformat()


def advance(previous, snapshot, now):
    """Count observed consumption conservatively; never invent a midnight sample."""
    validate_snapshot(snapshot, now)
    day = day_at(now)
    current = snapshot["used_percent"]
    uncertain = None
    coverage = "observed"
    if previous is None:
        # The current week's total includes all possible consumption earlier today.
        consumed = current
        coverage = "conservative: first reading counts current weekly usage"
    else:
        if previous["observed_at"] > now + 2:
            raise GuardError("Clock moved backwards; the daily baseline is unknown")
        if snapshot["observed_at"] < previous["observed_at"]:
            return previous
        new_day = previous["day"] != day
        consumed = 0 if new_day else previous["daily_points"]
        uncertain = None if new_day else previous["uncertain"]
        coverage = "conservative: boundary gap counts today" if new_day else previous["coverage"]
        if previous["plan"] != snapshot["plan"]:
            uncertain = "Plan changed; the daily quota denominator is unknown"
        elif previous["resets_at"] != snapshot["resets_at"]:
            consumed += current
            uncertain = "Quota reset between readings; daily consumption is incomplete"
        elif current < previous["used_percent"]:
            uncertain = "Quota decreased without a reported reset"
        else:
            consumed += current - previous["used_percent"]
    return {
        "version": 1, "day": day, "plan": snapshot["plan"],
        "used_percent": current, "resets_at": snapshot["resets_at"],
        "observed_at": snapshot["observed_at"], "daily_points": consumed,
        "uncertain": uncertain, "coverage": coverage,
        "manual_baseline": previous.get("manual_baseline") if previous else None,
    }


def default_state_dir():
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return root / "codex-daily-guard"


@contextmanager
def state_lock(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(directory / "state.lock", os.O_CREAT | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "a") as handle:
        deadline = time.monotonic() + 2
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise GuardError("Daily usage state is busy; retry the prompt")
                time.sleep(0.02)
        yield


def read_state(path):
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
        required = ("day", "plan", "used_percent", "resets_at", "observed_at", "daily_points", "uncertain", "coverage")
        if value.get("version") != 1 or any(k not in value for k in required):
            raise ValueError
        if type(value["daily_points"]) is not int or value["daily_points"] < 0:
            raise ValueError
        if type(value["used_percent"]) is not int or not 0 <= value["used_percent"] <= 100:
            raise ValueError
        if type(value["observed_at"]) not in (int, float) or type(value["resets_at"]) is not int:
            raise ValueError
        return value
    except (ValueError, TypeError, AttributeError):
        raise GuardError("Daily usage state is corrupt; inspect it before setting a baseline") from None


def save_state(path, state):
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(state, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def record(snapshot, directory, now, baseline=None, cap=CAP, warning=WARNING):
    validate_snapshot(snapshot, now)
    with state_lock(directory):
        path = directory / (snapshot["account_key"] + ".json")
        previous = read_state(path)
        state = advance(previous, snapshot, now)
        if baseline is not None:
            state["manual_baseline"] = {
                "at": now, "declared_points": baseline,
                "previous_points": state["daily_points"], "previous_uncertainty": state["uncertain"],
            }
            state["daily_points"] = baseline
            state["uncertain"] = None
            state["coverage"] = "manual: user supplied today's consumption"
        save_state(path, state)
    return decision(state, now, cap, warning)


def decision(state, now, cap=CAP, warning=WARNING):
    if cap == CAP:
        cap = CAP_BY_DAY.get(day_at(now), cap)
    tomorrow = datetime.fromtimestamp(now, KOREA).date() + timedelta(days=1)
    unblock = datetime.combine(tomorrow, datetime.min.time(), KOREA)
    points = state["daily_points"]
    allowed = state["uncertain"] is None and points < cap
    message = f"Codex daily usage: {points}/{cap} weekly percentage points; next day {unblock:%Y-%m-%d %H:%M} KST."
    if state["uncertain"]:
        message = state["uncertain"] + ". " + message
    elif not allowed:
        message = "Daily Codex cap reached. " + message
    return {
        "allowed": allowed, "warning": allowed and points >= warning,
        "daily_points": points, "remaining_points": max(0, cap - points),
        "day": state["day"], "coverage": state["coverage"],
        "uncertain": state["uncertain"], "unblock_at": unblock.isoformat(), "message": message,
    }


def hook_output(event, result):
    if not result["allowed"]:
        if event == "Stop":
            return {"continue": False, "stopReason": result["message"], "systemMessage": result["message"]}
        return {"decision": "block", "reason": result["message"], "systemMessage": result["message"]}
    return {"systemMessage": result["message"]} if result["warning"] else {}


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    action = arguments[0] if arguments else None
    parser = GuardParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    for name in ("status", "baseline", "hook"):
        child = subparsers.add_parser(name)
        child.add_argument("--state-dir", type=Path, default=default_state_dir())
        child.add_argument("--codex-bin", default=shutil.which("codex"))
        child.add_argument("--json", action="store_true")
        child.add_argument("--daily-cap", type=int, default=CAP, choices=range(1, 101), metavar="1..100")
        child.add_argument("--warn-at", type=int, default=WARNING, choices=range(100), metavar="0..99")
        # Explicit fixture inputs keep simulations and native-hook tests off the real quota.
        child.add_argument("--snapshot", type=Path, help="Use a local metadata fixture (testing)")
        child.add_argument("--now", type=float, help="Observation timestamp (testing)")
        if name == "baseline":
            child.add_argument("--used-today", type=int, required=True, choices=range(101), metavar="0..100")
    event = "UserPromptSubmit"
    try:
        if action == "hook":
            payload = json.load(sys.stdin)
            event = payload.get("hook_event_name")
            if event not in ("UserPromptSubmit", "Stop"):
                raise GuardError("Unexpected daily guard hook event")
        options = parser.parse_args(arguments)
        if options.warn_at >= options.daily_cap:
            raise GuardError("Warning threshold must be lower than the daily cap")
        now = options.now if options.now is not None else time.time()
        if options.snapshot:
            snapshot = json.loads(options.snapshot.read_text())
        else:
            if not options.codex_bin:
                raise GuardError("Codex is not installed")
            snapshot = asyncio.run(probe(options.codex_bin, ["-c", "features.hooks=false"]))
            now = time.time()
        result = record(snapshot, options.state_dir, now, getattr(options, "used_today", None),
                        cap=options.daily_cap, warning=options.warn_at)
        if options.action == "hook":
            print(json.dumps(hook_output(event, result)))
            return 0
        print(json.dumps(result, indent=2) if options.json else result["message"] + " " + result["coverage"])
        return 0
    except (GuardError, OSError, ValueError, KeyError, TypeError, AttributeError, asyncio.TimeoutError) as error:
        message = str(error) if isinstance(error, GuardError) else "Daily guard could not read metadata or usage state"
        if action == "hook":
            print(json.dumps(hook_output(event, {"allowed": False, "message": message})))
            return 0
        print("Codex daily usage hook: " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
