#!/usr/bin/env python3
"""Interactively find listening ports with ss and fzf."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass


PROCESS_RE = re.compile(r'\("(?P<program>[^"]+)",pid=(?P<pid>\d+)')


@dataclass(frozen=True)
class SocketEntry:
    protocol: str
    state: str
    local_address: str
    port: int
    pid: str = "-"
    program: str = "-"


def parse_local_endpoint(endpoint: str) -> tuple[str, int] | None:
    """Split an ss local endpoint into its address and numeric port."""
    try:
        address, port_text = endpoint.rsplit(":", 1)
        port = int(port_text)
    except (ValueError, TypeError):
        return None

    if not 0 <= port <= 65535:
        return None

    if address.startswith("[") and address.endswith("]"):
        address = address[1:-1]

    return address, port


def parse_processes(process_text: str) -> tuple[str, str]:
    """Extract unique PIDs and program names from ss process metadata."""
    matches = PROCESS_RE.findall(process_text)
    if not matches:
        return "-", "-"

    programs = list(dict.fromkeys(program for program, _ in matches))
    pids = list(dict.fromkeys(pid for _, pid in matches))
    return ",".join(pids), ",".join(programs)


def parse_ss_line(line: str) -> SocketEntry | None:
    """Parse one line produced by ``ss -H -lntup``."""
    parts = line.split(maxsplit=6)
    if len(parts) < 6:
        return None

    protocol, state, _, _, local_endpoint, _ = parts[:6]
    endpoint = parse_local_endpoint(local_endpoint)
    if endpoint is None:
        return None

    address, port = endpoint
    pid, program = parse_processes(parts[6] if len(parts) == 7 else "")
    return SocketEntry(
        protocol=protocol,
        state=state,
        local_address=address,
        port=port,
        pid=pid,
        program=program,
    )


def collect_entries(*, tcp: bool, udp: bool) -> list[SocketEntry]:
    """Collect listening TCP and bound UDP sockets from ss."""
    command = ["ss", "-H", "-l", "-n", "-p"]
    if tcp:
        command.append("-t")
    if udp:
        command.append("-u")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("ss is not installed; install the iproute2 package") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or f"exit status {error.returncode}"
        raise RuntimeError(f"ss failed: {detail}") from error

    entries = filter(None, (parse_ss_line(line) for line in result.stdout.splitlines()))
    return sorted(
        entries,
        key=lambda entry: (
            entry.port,
            entry.protocol,
            entry.local_address,
            entry.program,
            entry.pid,
        ),
    )


def format_entry(entry: SocketEntry) -> str:
    return (
        f"{entry.port:>5}  "
        f"{entry.protocol:<5}  "
        f"{entry.state:<8}  "
        f"{entry.local_address:<24.24}  "
        f"{entry.pid:<10.10}  "
        f"{entry.program}"
    )


def build_fzf_command(query: str) -> list[str]:
    command = [
        "fzf",
        "--no-sort",
        "--layout=reverse",
        "--border",
        "--cycle",
        "--exit-0",
        "--info=inline",
        "--prompt=ports> ",
        "--header= PORT  PROTO  STATE     LOCAL ADDRESS             PID         APPLICATION",
    ]
    if query:
        command.extend(["--query", query])
    return command


def select_entry(entries: Sequence[SocketEntry], query: str) -> SocketEntry | None:
    """Run fzf and return the entry matching its selected display row."""
    if shutil.which("fzf") is None:
        raise RuntimeError("fzf is not installed")

    rows = [format_entry(entry) for entry in entries]
    result = subprocess.run(
        build_fzf_command(query),
        input="\n".join(rows) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode in (1, 130) or not result.stdout.strip():
        return None
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise RuntimeError(f"fzf failed: {detail}")

    selected_row = result.stdout.rstrip("\n")
    try:
        return entries[rows.index(selected_row)]
    except ValueError as error:
        raise RuntimeError("fzf returned an unknown selection") from error


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fuzzily find listening TCP and bound UDP ports.",
    )
    protocols = parser.add_argument_group("protocol filters")
    protocols.add_argument("-t", "--tcp", action="store_true", help="show only TCP")
    protocols.add_argument("-u", "--udp", action="store_true", help="show only UDP")
    parser.add_argument(
        "query",
        nargs="*",
        help="initial fuzzy-search query",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    tcp = args.tcp or not args.udp
    udp = args.udp or not args.tcp

    try:
        entries = collect_entries(tcp=tcp, udp=udp)
        if not entries:
            print("No listening TCP or bound UDP ports found.", file=sys.stderr)
            return 0

        selected = select_entry(entries, " ".join(args.query))
    except RuntimeError as error:
        print(f"ports: {error}", file=sys.stderr)
        return 1

    if selected is not None:
        print(selected.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
