#!/usr/bin/env bash
set -euo pipefail

HOST="${MDSERVE_HOST:-0.0.0.0}"
DEFAULT_PORT="${MDSERVE_PORT:-8000}"
SEARCH_DIR="${1:-.}"

if [[ ! "$DEFAULT_PORT" =~ ^[0-9]+$ ]] || ((10#$DEFAULT_PORT < 1 || 10#$DEFAULT_PORT > 65535)); then
  DEFAULT_PORT=8000
fi

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing dependency: $1" >&2
    exit 1
  }
}

find_markdown_files() {
  if command -v fd >/dev/null 2>&1; then
    fd --type f --extension md --extension markdown . "$SEARCH_DIR"
  elif command -v fdfind >/dev/null 2>&1; then
    fdfind --type f --extension md --extension markdown . "$SEARCH_DIR"
  else
    find "$SEARCH_DIR" -type f \( -iname '*.md' -o -iname '*.markdown' \) -print
  fi
}

shell_quote_command() {
  local quoted
  printf -v quoted '%q ' "$@"
  printf '%s\n' "${quoted% }"
}

finish_atuin_history() {
  local status=$?

  if [[ -n "${atuin_history_id:-}" ]]; then
    atuin history end --exit "$status" "$atuin_history_id" >/dev/null 2>&1 || true
  fi
}

prompt_port() {
  local input port_num

  if ! { : </dev/tty >/dev/tty; } 2>/dev/null; then
    printf '%s\n' "$DEFAULT_PORT"
    return
  fi

  while true; do
    printf 'Port [%s]: ' "$DEFAULT_PORT" >/dev/tty
    IFS= read -r input </dev/tty || input=""
    input="${input:-$DEFAULT_PORT}"

    if [[ "$input" =~ ^[0-9]+$ ]]; then
      port_num=$((10#$input))
      if ((port_num >= 1 && port_num <= 65535)); then
        printf '%s\n' "$port_num"
        return
      fi
    fi

    printf 'Invalid port: %s (expected 1-65535)\n' "$input" >/dev/tty
  done
}

require fzf
require mdserve
require atuin
require realpath

bash_path="$(command -v bash)"
PORT="$(prompt_port)"

mapfile -t files < <(find_markdown_files)

if ((${#files[@]} == 0)); then
  echo "No markdown files found in: $SEARCH_DIR" >&2
  exit 1
fi

if ! selection="$(
  printf '%s\n' "${files[@]}" |
    SHELL="$bash_path" fzf --height 70% --reverse --no-multi \
      --prompt="mdserve> " \
      --header="Select a markdown file to serve on ${HOST}:${PORT}" \
      --preview='if command -v bat >/dev/null 2>&1; then bat --color=always --style=numbers --line-range=:160 -- {}; else sed -n "1,160p" -- {}; fi' \
      --preview-window=right,60%,border
)"; then
  exit 0
fi

[[ -n "${selection:-}" ]] || exit 0

selected_path="$(realpath -- "$selection")"
cmd=(mdserve --hostname "$HOST" --port "$PORT" "$selected_path")
history_cmd="$(shell_quote_command "${cmd[@]}")"

atuin_history_id=""
if atuin_history_id="$(atuin history start "$history_cmd" 2>/dev/null)"; then
  trap finish_atuin_history EXIT
else
  echo "Warning: failed to add command to Atuin history" >&2
fi

printf 'Serving: %s\n' "$selected_path"
printf 'Atuin command: %s\n' "$history_cmd"

set +e
"${cmd[@]}"
status=$?
set -e

exit "$status"
