#!/usr/bin/env python3
"""Bounded model checker for herdr-tab-status's tab-name journal.

It runs the real Updater code from private_dot_local/bin/executable_herdr-tab-status.
Only two things are replaced: `request` (the Herdr socket call) becomes an in-memory
Herdr, and `time` becomes a model clock. Breadth-first search then tries every order
of these steps, up to --depth steps and --faults faults per trace:

  update        the worker's update(): snapshot, journal save, tab.rename calls
  stop          the worker's restore() on a stop request, or `stop` with no worker
  start         a new worker loads the on-disk journal (after a crash or stop)
  crash         the worker process dies between steps
  user renames  a plain new name, or an edit that keeps the managed number and suffix
  agent change  a tab's agent appears, changes state, or exits
  move          the two tabs swap places
  tick          the clock advances one minute (ages in suffixes change)

Faults inside update and stop: the journal save raises OSError; the process dies
right after the save; a tab.rename is rejected, has its reply lost after Herdr
applied it, or the process dies just before or just after Herdr applies it.

Properties, checked after every step:
  NameRecoverable  for every tab, original_label(live label, on-disk journal record)
                   returns the name the user chose. A crash at this instant can
                   always restore the user's name.
  StopRestores     after a stop that finished without a fault, every tab shows the
                   name the user chose, and the on-disk journal has no tab records.
  JournalReadable  a starting worker can load the on-disk journal.

Assumption: user renames happen between updater steps. The documented race (a
manual rename between the updater's snapshot and its rename request) is out of scope.

Exit status: 0 when no property fails within the bounds, 1 on a counterexample,
2 for usage errors.
"""

import argparse
import collections
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import tempfile
import time as real_time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCRIPT = ROOT / "private_dot_local/bin/executable_herdr-tab-status"
SOCKET = "/model/herdr.sock"
DECORATED = re.compile(r"^(\d+)(?: .*?)?( \[[^\]]*\])$")


class Crash(BaseException):
    """The process dies; nothing after this point runs."""


def load(script):
    loader = importlib.machinery.SourceFileLoader("herdr_tab_status_under_check", str(script))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


class Herdr:
    """In-memory Herdr: renames change later snapshots; faults fire on one call."""

    def __init__(self, module, tabs, clock):
        self.module = module
        self.tabs = [dict(tab) for tab in tabs]
        self.clock = clock
        self.fault = None  # (kind, rename_index) for this step
        self.renames = 0
        self.fired = False
        self.log = []

    def snapshot(self):
        tabs, agents = [], []
        for tab in self.tabs:
            tabs.append({
                "tab_id": tab["id"], "workspace_id": "w1", "number": tab["number"],
                "label": tab["label"], "agent_status": tab["agent"] or "idle",
            })
            if tab["agent"]:
                agents.append({"tab_id": tab["id"], "agent": "codex", "agent_status": tab["agent"]})
        return {"workspaces": [{"workspace_id": "w1", "pane_count": len(tabs)}],
                "tabs": tabs, "agents": agents, "panes": []}

    def request(self, _socket, method, params):
        if method == "session.snapshot":
            return {"snapshot": self.snapshot()}
        if method != "tab.rename":
            return {}
        self.renames += 1
        tab = next(tab for tab in self.tabs if tab["id"] == params["tab_id"])
        kind = self.fault[0] if self.fault and self.fault[1] == self.renames else None
        if kind:
            self.fired = True
        if kind == "reject":
            self.log.append(f"tab.rename {tab['id']} -> {params['label']!r} rejected")
            raise self.module.HerdrError("rejected")
        if kind == "crash-before":
            self.log.append(f"process dies before tab.rename {tab['id']} -> {params['label']!r}")
            raise Crash
        tab["label"] = params["label"]
        if kind == "lost":
            self.log.append(f"tab.rename {tab['id']} -> {params['label']!r} applied, reply lost")
            raise self.module.HerdrError("incomplete response to tab.rename")
        if kind == "crash-after":
            self.log.append(f"tab.rename {tab['id']} -> {params['label']!r} applied, then the process dies")
            raise Crash
        self.log.append(f"tab.rename {tab['id']} -> {params['label']!r}")
        return {}


class Model:
    """States are (tabs, disk journal, worker memory, chosen names, clock).

    Worker memory is None when the next worker step would load exactly the disk
    journal: no worker is running, or the running worker's journal equals the disk.
    It differs from the disk only after a failed journal save.
    """

    def __init__(self, module, directory, clock_max, save_faults=True):
        self.module = module
        self.save_faults = save_faults
        self.directory = directory
        self.state_path = directory / "state.json"
        self.clock_max = clock_max
        self.clock = 0
        module.time = types.SimpleNamespace(time=lambda: self.clock, monotonic=lambda: self.clock)
        # Process crashes keep os.replace atomic, so durability (fsync) is out of
        # scope and skipped for speed. Every other os call is the real one.
        module.os = types.SimpleNamespace(**{n: getattr(os, n) for n in dir(os) if not n.startswith("__")})
        module.os.fsync = lambda _fd: None

    def disk(self):
        return self.state_path.read_text() if self.state_path.exists() else None

    def set_disk(self, text):
        if text is None:
            self.state_path.unlink(missing_ok=True)
        else:
            self.state_path.write_text(text)

    @staticmethod
    def records(text):
        return json.loads(text)["tabs"] if text else {}

    def run(self, state, command, fault):
        """Run update or restore from `state` with at most one fault; return (next state, step)."""
        tabs, disk, memory, names, clock = state
        self.clock = clock
        self.set_disk(disk)
        herdr = Herdr(self.module, [json.loads(tab) for tab in tabs], clock)
        herdr.fault = fault
        self.module.request = herdr.request
        try:
            updater = self.module.Updater(SOCKET, self.directory)
        except (OSError, ValueError, KeyError, self.module.HerdrError) as error:
            return ("UNREADABLE", str(error)), f"{command} cannot load the journal: {error}"
        if memory is not None:
            updater.tabs = json.loads(memory)
        real_save = updater.save

        def save():
            if fault and fault[0] == "save-fails":
                herdr.fired = True
                herdr.log.append("journal save raises OSError")
                raise OSError(28, "No space left on device")
            real_save()
            herdr.log.append("journal saved")
            if fault and fault[0] == "crash-after-save":
                herdr.fired = True
                herdr.log.append("process dies after the journal save")
                raise Crash

        updater.save = save
        outcome, alive = "ok", command == "update"  # a worker exits after restore
        try:
            getattr(updater, command)()
        except Crash:
            outcome, alive = "crash", False
        except (OSError, ValueError, KeyError, self.module.HerdrError) as error:
            outcome = f"error ({type(error).__name__}: {error})"
        if fault and not herdr.fired:
            return None, None  # the fault never triggered: same as the fault-free step
        next_disk = self.disk()
        next_memory = json.dumps(updater.tabs, sort_keys=True) if alive else None
        if next_memory == json.dumps(self.records(next_disk), sort_keys=True):
            next_memory = None
        next_state = (tuple(json.dumps(tab, sort_keys=True) for tab in herdr.tabs),
                      next_disk, next_memory, names, clock)
        what = "stop: restore()" if command == "restore" else "update()"
        return next_state, f"{what} -> {outcome}: {'; '.join(herdr.log) or 'no renames'}"

    def successors(self, state, faults_left):
        """Yield (next state, step, uses a fault)."""
        tabs, disk, memory, names, clock = state
        decoded = [json.loads(tab) for tab in tabs]
        faults = [None]
        if faults_left:
            faults += [("crash-after-save", 0)] + ([("save-fails", 0)] if self.save_faults else [])
            faults += [(kind, k) for kind in ("reject", "lost", "crash-before", "crash-after")
                       for k in (1, 2)]
        for command in ("update", "restore"):
            for fault in faults:
                successor, step = self.run(state, command, fault)
                if successor is not None:
                    yield successor, step, fault is not None
        if memory is not None and faults_left:
            yield (tabs, disk, None, names, clock), "crash: the worker dies with an unsaved journal", True
        for index, tab in enumerate(decoded):
            if names[index] != "notes":
                renamed = [dict(t) for t in decoded]
                renamed[index]["label"] = "notes"
                yield self.with_tabs(state, renamed, index, "notes"), f"user renames {tab['id']} to 'notes'", False
                match = DECORATED.match(tab["label"])
                if match and tab["label"] != names[index]:
                    edited = [dict(t) for t in decoded]
                    edited[index]["label"] = f"{match.group(1)} notes{match.group(2)}"
                    yield (self.with_tabs(state, edited, index, "notes"),
                           f"user edits {tab['id']} to {edited[index]['label']!r}, keeping number and suffix", False)
            for agent in (None, "working", "blocked"):
                if agent != tab["agent"]:
                    changed = [dict(t) for t in decoded]
                    changed[index]["agent"] = agent
                    yield self.with_tabs(state, changed), f"agent in {tab['id']} becomes {agent or 'absent'}", False
        yield self.with_tabs(state, decoded[::-1]), "user swaps the two tabs", False
        if clock < self.clock_max * 60:
            yield (tabs, disk, memory, names, clock + 60), "one minute passes", False

    @staticmethod
    def with_tabs(state, tabs, index=None, name=None):
        old_tabs, disk, memory, names, clock = state
        # Names follow tabs by id, so a swap keeps each tab's chosen name.
        by_id = {json.loads(t)["id"]: n for t, n in zip(old_tabs, names)}
        if index is not None:
            by_id[tabs[index]["id"]] = name
        return (tuple(json.dumps(t, sort_keys=True) for t in tabs), disk, memory,
                tuple(by_id[t["id"]] for t in tabs), clock)

    def violation(self, state, step):
        if state[0] == "UNREADABLE":
            return f"JournalReadable: a worker cannot load the journal: {state[1]}"
        tabs, disk, _memory, names, _clock = state
        records = self.records(disk)
        for tab, name in zip((json.loads(t) for t in tabs), names):
            base, _owned = self.module.original_label(tab["label"], records.get(tab["id"]))
            if base != name:
                return (f"NameRecoverable: {tab['id']} shows {tab['label']!r}; the on-disk journal "
                        f"recovers {base!r}, but the user chose {name!r}")
        if step.startswith("stop: restore() -> ok"):
            for tab, name in zip((json.loads(t) for t in tabs), names):
                if tab["label"] != name:
                    return f"StopRestores: after stop, {tab['id']} shows {tab['label']!r}, not {name!r}"
            if records:
                return f"StopRestores: after stop, the journal still has records for {sorted(records)}"
        return None


def describe(state):
    if state[0] == "UNREADABLE":
        return "journal unreadable"
    tabs, disk, memory, names, clock = state
    labels = ", ".join(f"{json.loads(t)['id']}={json.loads(t)['label']!r}" for t in tabs)
    journal = {k: v["base"] for k, v in json.loads(disk)["tabs"].items()} if disk else None
    worker = "same as disk" if memory is None else "differs from disk (unsaved)"
    return f"labels: {labels} | disk journal bases: {journal} | worker journal: {worker} | user chose: {list(names)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT,
                        help="herdr-tab-status file to check (default: this checkout's)")
    parser.add_argument("--depth", type=int, default=5, help="maximum steps per trace (default 5)")
    parser.add_argument("--faults", type=int, default=2, help="maximum faults per trace (default 2)")
    parser.add_argument("--ticks", type=int, default=1, help="maximum minutes the clock advances (default 1)")
    parser.add_argument("--no-save-faults", action="store_true",
                        help="leave out journal save failures (known finding F1 in SKILL.md)")
    args = parser.parse_args()
    if not args.script.is_file():
        parser.error(f"no such script: {args.script}")

    module = load(args.script)
    started = real_time.monotonic()
    shm = Path("/dev/shm")
    with tempfile.TemporaryDirectory(prefix="herdr-tab-labels-", dir=shm if shm.is_dir() else None) as scratch:
        model = Model(module, Path(scratch), args.ticks, save_faults=not args.no_save_faults)
        initial_tabs = (
            {"id": "w1:t1", "number": 1, "label": "work", "agent": "working"},
            {"id": "w1:t2", "number": 2, "label": "7", "agent": None},
        )
        initial = (tuple(json.dumps(t, sort_keys=True) for t in initial_tabs), None, None, ("work", "7"), 0)
        parents = {initial: (None, "initial: no journal yet")}
        used = {initial: 0}  # fewest faults spent to reach each state
        frontier = collections.deque([(initial, 0)])
        transitions = 0
        while frontier:
            state, depth = frontier.popleft()
            if depth >= args.depth:
                continue
            for successor, step, faulty in model.successors(state, used[state] < args.faults):
                transitions += 1
                spent = used[state] + faulty
                if successor in used and used[successor] <= spent:
                    continue
                first_visit = successor not in used
                used[successor] = spent
                if first_visit:
                    parents[successor] = (state, step)
                    problem = model.violation(successor, step)
                    if problem:
                        trace, cursor = [], successor
                        while cursor is not None:
                            parent, how = parents[cursor]
                            trace.append((how, cursor))
                            cursor = parent
                        print(f"FAIL {problem}\n\nShortest counterexample ({len(trace) - 1} steps):")
                        for number, (how, at) in enumerate(reversed(trace)):
                            print(f"  {number}. {how}\n     {describe(at)}")
                        print(f"\n{len(used)} states, {transitions} transitions, "
                              f"{real_time.monotonic() - started:.1f}s; script {args.script}")
                        return 1
                if successor[0] != "UNREADABLE":
                    frontier.append((successor, depth + 1))
    print(f"PASS NameRecoverable, StopRestores, JournalReadable within depth {args.depth}, "
          f"{args.faults} faults, {args.ticks} minute(s){' (no save faults)' if args.no_save_faults else ''}")
    print(f"{len(used)} states, {transitions} transitions, {real_time.monotonic() - started:.1f}s; "
          f"script {args.script}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
