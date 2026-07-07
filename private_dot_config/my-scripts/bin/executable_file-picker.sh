#!/usr/bin/env bash
set -euo pipefail

max_depth=""
sep=$'\037'

while (($# > 0)); do
  case "$1" in
    --max-depth)
      if (($# < 2)); then
        printf 'file-picker.sh: --max-depth requires a value\n' >&2
        exit 2
      fi
      max_depth=$2
      shift 2
      ;;
    --max-depth=*)
      max_depth=${1#*=}
      shift
      ;;
    --)
      shift
      break
      ;;
    -*)
      printf 'file-picker.sh: unknown option: %s\n' "$1" >&2
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

query="${*:-}"

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'file-picker.sh: required command not found: %s\n' "$1" >&2
    exit 127
  fi
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "$PWD" "$1" ;;
  esac
}

eza_line() {
  local file=$1
  local line

  line="$(
    eza -a -l --no-permissions --no-user --icons=always \
      --color=always --show-symlinks -- "$file" 2>/dev/null \
      | sed -n '1p'
  )"

  if [[ -n $line ]]; then
    printf '%s\n' "$line"
  else
    printf '%s\n' "$file"
  fi
}

rows() {
  local file abs display
  local -a fd_args=(
    --type f
    --type l
    --hidden
    --follow
    --exclude .git
    --exclude .jj
  )

  if [[ -n $max_depth ]]; then
    fd_args+=(--max-depth "$max_depth")
  fi

  fd "${fd_args[@]}" \
  | while IFS= read -r file; do
      [[ -n $file ]] || continue
      abs=$(abs_path "$file")
      display=$(eza_line "$file")
      printf '%s%s%s\n' "$abs" "$sep" "$display"
    done
}

main() {
  require fd
  require fzf
  require eza

  local selected
  if ! selected="$(
    rows \
    | fzf --ansi --height 60% --reverse --query "$query" \
        --delimiter "$sep" --with-nth 2 --accept-nth 1
  )"; then
    exit 0
  fi

  selected="$(printf '%s\n' "$selected" | sed -n '1p')"
  [[ -n $selected ]] || exit 0
  printf '%s\n' "$selected"
}

main "$@"
