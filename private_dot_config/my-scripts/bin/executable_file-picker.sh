#!/usr/bin/env bash
set -euo pipefail

max_depth=""
sep=$'\037'
tmp_dir=""

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

cleanup() {
  if [[ -n ${tmp_dir:-} ]]; then
    rm -rf "$tmp_dir"
  fi
}

write_rows() {
  local tmp_files=$1
  local tmp_abs=$2
  local tmp_display=$3
  local tmp_rows=$4
  local file
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

  fd "${fd_args[@]}" >"$tmp_files"
  [[ -s $tmp_files ]] || return 0

  while IFS= read -r file; do
    [[ -n $file ]] || continue
    abs_path "$file"
  done <"$tmp_files" >"$tmp_abs"

  if ! eza -a -l --no-permissions --no-user --icons=always \
      --color=always --show-symlinks --sort=none --stdin \
      <"$tmp_files" >"$tmp_display" 2>/dev/null; then
    cp "$tmp_files" "$tmp_display"
  fi

  paste -d "$sep" "$tmp_abs" "$tmp_display" >"$tmp_rows"
}

main() {
  require fd
  require fzf
  require eza

  local tmp_files tmp_abs tmp_display tmp_rows
  tmp_dir=$(mktemp -d)
  trap cleanup EXIT
  tmp_files=$tmp_dir/files
  tmp_abs=$tmp_dir/abs
  tmp_display=$tmp_dir/display
  tmp_rows=$tmp_dir/rows

  write_rows "$tmp_files" "$tmp_abs" "$tmp_display" "$tmp_rows"
  [[ -s $tmp_rows ]] || exit 0

  local selected
  if ! selected="$(
    fzf --ansi --height 60% --reverse --query "$query" \
        --delimiter "$sep" --with-nth 2 --accept-nth 1 \
        <"$tmp_rows"
  )"; then
    exit 0
  fi

  selected="$(printf '%s\n' "$selected" | sed -n '1p')"
  [[ -n $selected ]] || exit 0
  printf '%s\n' "$selected"
}

main "$@"
