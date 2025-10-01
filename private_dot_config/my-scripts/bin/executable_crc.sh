#!/usr/bin/env bash
# cgdb-recent-core: open the most recent core* with cgdb, inferring the executable
# Usage:
#   cgdb-recent-core               # auto-detect executable from core
#   cgdb-recent-core /path/to/exe  # explicitly provide executable (fallback)

set -euo pipefail

# --- helpers ---------------------------------------------------------------

err() { printf 'Error: %s\n' "$*" >&2; }

have() { command -v "$1" >/dev/null 2>&1; }

# Pick the most recent file matching core*
find_recent_core() {
  # macOS/BSD and GNU both support -t (sort by mtime, newest first)
  /bin/ls -t core* 2>/dev/null | head -n 1 || true
}

# Extract executable path from `file` output (Linux "execfn: '...'" style)
extract_exec_from_core() {
  local core="$1"
  # Try to pull execfn: '...'
  local exe
  exe="$(file "$core" 2>/dev/null | sed -n "s/.*execfn: '\([^']*\)'.*/\1/p")" || true
  printf '%s' "$exe"
}

usage() {
  cat <<'EOF'
cgdb-recent-core: open the most recent core* with cgdb

Usage:
  cgdb-recent-core               # auto-detect the executable via `file`
  cgdb-recent-core /path/to/exe  # provide the executable explicitly (fallback)

Notes:
  - Looks for files named 'core*' in the current directory.
  - Tries to parse the executable path from `file` output (execfn: '...').
  - If parsing fails or you're on a system where `file` doesn't include execfn,
    pass the executable path as the first argument.
EOF
}

# --- main ------------------------------------------------------------------

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! have cgdb; then
  err "cgdb is not installed or not in PATH."
  exit 127
fi

# core_file="$(find_recent_core)"
core_file="$(/bin/ls -t core* 2> /dev/null | fzf --height 60% --reverse)"
if [[ -z "$core_file" ]]; then
  err "No core files found in the current directory."
  exit 1
fi

# Determine executable: prefer user arg; else try to parse from core
executable="${1:-}"
if [[ -z "$executable" ]]; then
  executable="$(extract_exec_from_core "$core_file")"
fi

if [[ -z "$executable" ]]; then
  err "Could not determine the executable from $core_file."
  err "Tip: run 'file $core_file' to inspect, or pass the executable explicitly:"
  err "     cgdb-recent-core /path/to/executable"
  exit 1
fi

printf 'Analyzing core file: %s with executable: %s\n' "$core_file" "$executable"
exec cgdb "$executable" "$core_file"

