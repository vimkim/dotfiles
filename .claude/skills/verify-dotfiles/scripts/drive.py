#!/usr/bin/env python3
"""Drive one interactive shell inside a verify-dotfiles run, the way a user types.

The shell starts in a pseudo-terminal with the run's scrubbed environment
(run.env), so it reads the disposable home's startup files and nothing from
the live home. Every byte the terminal shows is saved as evidence.

Usage:
  drive.py RUN_DIR --shell nu|bash|zsh [options] STEP [STEP ...]

Steps (run in order):
  cmd:TEXT     Paste TEXT, press Enter, and wait until it finishes.
               Records the command's exit status.
  keys:TEXT    Type TEXT with no Enter. Python escapes work: \\r Enter,
               \\x1b Escape, \\t Tab, \\x03 Ctrl-C, \\x1b[B Down.
  expect:RE    Wait until the screen text since the last checkpoint matches
               the regular expression RE. Then move the checkpoint.
  sleep:SECS   Wait SECS seconds.

Options:
  --label NAME   Evidence file prefix (default: <shell>-<time>).
  --cwd DIR      Start directory (default: RUN_DIR/work).
  --login        Start a login shell (bash -l, zsh -l, nu -l).
  --timeout S    Seconds allowed for startup and for each step (default 30).
  --cols N --rows N   Terminal size (default 120x40).

Exit status: 0 when every step finished and the shell exited by itself
after `exit`; 1 when a step timed out or the shell had to be killed;
2 for usage errors. A command's own nonzero status does not fail the
drive; read it in the JSON evidence.
"""

import argparse
import codecs
import fcntl
import json
import os
import pty
import re
import select
import signal
import struct
import sys
import termios
import time
from pathlib import Path

ANSI = re.compile(
    rb"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC ... BEL or ST
    rb"|\x1b\[[0-?]*[ -/]*[@-~]"  # CSI
    rb"|\x1b[PX^_][^\x1b]*\x1b\\"  # DCS, SOS, PM, APC
    rb"|\x1b[@-Z\\-_0-9=>]"  # other two-byte escapes, including ESC 7 and ESC 8
)
# Terminal queries that line editors and fzf send and then wait on.
# Each occurrence gets one answer, in order.
QUERY = re.compile(rb"\x1b\[6n|\x1b\[0?c|\x1b\[\?(\d+)\$p")


def answer(query: re.Match, raw: bytes, rows: int) -> bytes:
    if query.group(0) == b"\x1b[6n":  # cursor position: report the bottom row
        return f"\x1b[{rows};1R".encode()
    if query.group(1):  # DECRQM: report the mode as last set in this terminal
        mode = query.group(1)
        before = raw[: query.start()]
        on, off = before.rfind(b"\x1b[?" + mode + b"h"), before.rfind(b"\x1b[?" + mode + b"l")
        state = b"0" if on == off == -1 else (b"1" if on > off else b"2")
        return b"\x1b[?" + mode + b";" + state + b"$y"
    return b"\x1b[?62;22c"  # primary device attributes


READY = b"\x1b[?2004h"  # bracketed paste on: the line editor is reading

# Marker commands: the typed text never contains the marker it prints,
# so the echoed keystrokes cannot satisfy the wait.
MARKERS = {
    "bash": "printf '\\n__VD_%s_%s__\\n' $((N+1)) $?",
    "zsh": "printf '\\n__VD_%s_%s__\\n' $((N+1)) $?",
    "nu": 'print $"\\n__VD_(N + 1)_($env.LAST_EXIT_CODE)__"',
}


MOVES = re.compile(rb"\x1b\[[0-9;]*[ABEFHf]|\x1b\[[0-9]*d")  # cursor moves between rows


def paste(line: str) -> bytes:
    """A command line as one bracketed paste, then Enter.

    Each line editor inserts a paste as one event, so the transcript shows
    one redraw instead of one per character, and no key binding fires
    mid-line. Use keys: to type character by character.
    """
    return b"\x1b[200~" + line.encode() + b"\x1b[201~\r"


def clean(data: bytes) -> str:
    """Flatten terminal output to plain text without losing drawn text.

    Cursor moves and carriage returns become line breaks, so full-screen
    programs such as fzf leave every row they drew. Overwritten text stays
    visible too; read the .typescript file for exact rendering.
    """
    text = ANSI.sub(b"", MOVES.sub(b"\n", data)).decode("utf-8", "replace")
    while "\b" in text:  # apply backspaces the way the terminal does
        text, count = re.subn(r"[^\n\b]\x08", "", text)
        if not count:
            text = text.replace("\b", "")
    text = text.replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


class Drive:
    def __init__(self, args):
        self.args = args
        self.rows, self.cols = args.rows, args.cols
        self.raw = bytearray()
        self.checkpoint = 0
        self.serial = 1000
        self.marker_sent_at = 0
        self.keys_mark = None
        self.scanned = 0
        self.steps = []

    def spawn(self, env):
        shell = self.args.shell
        argv = [shell, "-l"] if self.args.login else [shell]
        if shell == "nu" and self.args.login:
            argv = ["nu", "--login"]
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(self.args.cwd)
            os.execvpe(argv[0], argv, env)
        self.pid, self.fd = pid, fd
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", self.rows, self.cols, 0, 0))

    def pump(self, timeout):
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return False
        try:
            chunk = os.read(self.fd, 65536)
        except OSError:
            chunk = b""
        if not chunk:
            raise EOFError
        self.raw += chunk
        # Rescan a few old bytes so a query split across reads is still seen.
        start = max(self.scanned - 8, 0)
        for query in QUERY.finditer(self.raw, start):
            if query.end() > self.scanned:
                os.write(self.fd, answer(query, bytes(self.raw), self.rows))
        self.scanned = len(self.raw)
        return True

    def write(self, data: bytes):
        for i in range(0, len(data), 64):
            os.write(self.fd, data[i : i + 64])
            time.sleep(0.01)

    def wait_for(self, pattern, timeout):
        deadline = time.monotonic() + timeout
        regex = re.compile(pattern, re.M)
        while True:
            match = regex.search(clean(bytes(self.raw[self.checkpoint :])))
            if match:
                return match
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            self.pump(min(remaining, 0.2))

    def wait_editor(self, since, timeout):
        """Wait for the line editor to start reading a new line.

        Reedline (nu), readline (bash 5.1+), and zle (zsh) turn on bracketed
        paste once per prompt. Keys typed before that can be discarded
        (reedline flushes typeahead), so every typed line waits for it.
        """
        deadline = time.monotonic() + timeout
        while READY not in self.raw[since:]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            self.pump(min(remaining, 0.2))
        return True

    def marker(self):
        self.serial += 1
        line = MARKERS[self.args.shell].replace("N", str(self.serial - 1), 1)
        return line, rf"__VD_{self.serial}_(-?\d*)__"

    def settle(self, timeout):
        """Report the last exit status, then wait for the next prompt."""
        line, pattern = self.marker()
        mark = self.marker_sent_at = len(self.raw)
        self.write(paste(line))
        match = self.wait_for(pattern, timeout)
        if match and self.wait_editor(mark, timeout):
            self.checkpoint = len(self.raw)
            return match
        return None

    def run_step(self, step):
        kind, _, value = step.partition(":")
        start = time.monotonic()
        record = {"step": step, "ok": True}
        if kind == "cmd":
            if self.keys_mark is not None:
                # After raw keys (a picker, a TUI), wait for the shell prompt again.
                if not self.wait_editor(self.keys_mark, self.args.timeout):
                    record["ok"] = False
                    record["note"] = "the shell prompt did not return after the last keys step"
                    self.steps.append(record)
                    return False
                self.keys_mark = None
            mark = len(self.raw)
            self.write(paste(value))
            match = self.settle(self.args.timeout) if self.wait_editor(mark, self.args.timeout) else None
            end = self.marker_sent_at if match else len(self.raw)
            record["output"] = clean(bytes(self.raw[mark:end]))
            if match:
                status = match.group(1)
                record["status"] = int(status) if status.lstrip("-").isdigit() else None
            else:
                record["ok"] = False
        elif kind == "keys":
            self.keys_mark = len(self.raw)
            keys = codecs.decode(value.encode("latin-1", "backslashreplace"), "unicode_escape")
            self.write(keys.encode())
        elif kind == "expect":
            match = self.wait_for(value, self.args.timeout)
            record["ok"] = bool(match)
            if match:
                record["matched"] = match.group(0)
                self.checkpoint = len(self.raw)
        elif kind == "sleep":
            end = time.monotonic() + float(value)
            while time.monotonic() < end:
                self.pump(min(0.2, end - time.monotonic()))
        else:
            raise SystemExit(f"drive.py: unknown step {step!r}")
        record["seconds"] = round(time.monotonic() - start, 3)
        self.steps.append(record)
        return record["ok"]

    def finish(self):
        self.write(b"exit\r")
        deadline = time.monotonic() + 10
        status = None
        while time.monotonic() < deadline:
            try:
                self.pump(0.2)
            except EOFError:
                pass
            done, code = os.waitpid(self.pid, os.WNOHANG)
            if done:
                status = os.waitstatus_to_exitcode(code)
                break
        killed = status is None
        if killed:
            # Kill only the session this drive created; pty.fork made it a leader.
            try:
                os.killpg(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _, code = os.waitpid(self.pid, 0)
            status = os.waitstatus_to_exitcode(code)
        return status, killed


def load_env(run: Path, shell: str):
    env = {}
    for line in (run / "run.env").read_text().splitlines():
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key] = value
    env["SHELL"] = shell
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--shell", required=True, choices=sorted(MARKERS))
    parser.add_argument("--label")
    parser.add_argument("--cwd")
    parser.add_argument("--login", action="store_true")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--cols", type=int, default=120)
    parser.add_argument("--rows", type=int, default=40)
    parser.add_argument("steps", nargs="*")
    args = parser.parse_args()

    run = args.run.resolve()
    if not (run / "run.env").is_file():
        parser.error(f"{run} is not a verify-dotfiles run (no run.env); run launch first")
    env = load_env(run, args.shell)
    args.cwd = args.cwd or str(run / "work")
    label = args.label or f"{args.shell}-{time.strftime('%H%M%S')}"
    evidence = run / "evidence"
    evidence.mkdir(exist_ok=True)

    drive = Drive(args)
    drive.spawn(env)
    started = time.monotonic()
    ok = True
    try:
        ready = drive.wait_editor(0, args.timeout) and drive.settle(args.timeout)
        drive.steps.append({"step": "startup", "ok": bool(ready), "seconds": round(time.monotonic() - started, 3),
                            "output": clean(bytes(drive.raw))})
        ok = bool(ready)
        for step in args.steps if ok else []:
            if not drive.run_step(step):
                ok = False
                break
    except EOFError:
        ok = False
        drive.steps.append({"step": "eof", "ok": False, "note": "shell closed the terminal early"})
    status, killed = drive.finish()
    ok = ok and not killed

    (evidence / f"{label}.typescript").write_bytes(bytes(drive.raw))
    (evidence / f"{label}.txt").write_text(clean(bytes(drive.raw)))
    report = {
        "label": label,
        "shell": args.shell,
        "login": args.login,
        "cwd": args.cwd,
        "ok": ok,
        "shell_exit": status,
        "killed": killed,
        "steps": drive.steps,
    }
    (evidence / f"{label}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for record in drive.steps:
        mark = "ok " if record["ok"] else "FAIL"
        extra = f" status={record['status']}" if "status" in record else ""
        print(f"{mark} {record['step']}{extra} ({record.get('seconds', 0)}s)")
    print(f"evidence: {evidence / label}.{{txt,json,typescript}}")
    print(f"shell exit={status} killed={killed} -> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
