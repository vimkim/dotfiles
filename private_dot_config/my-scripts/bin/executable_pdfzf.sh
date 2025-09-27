#!/usr/bin/env bash

set -euo pipefail

SEARCH_DIR="${1:-${BOOKS_DIR:-$HOME/Documents/NOW_READING}}"

require() { command -v "$1" >/dev/null 2>&1 || {
  echo "Missing dependency: $1" >&2
  exit 1
}; }
require fzf

# Gather files
if command -v fd >/dev/null 2>&1; then
  mapfile -t files < <(fd -t f -e pdf -e epub . "$SEARCH_DIR")
else
  mapfile -t files < <(find "$SEARCH_DIR" -type f \( -iname '*.pdf' -o -iname '*.epub' \) 2>/dev/null)
fi
((${#files[@]})) || {
  echo "No documents found in: $SEARCH_DIR"
  exit 1
}

# Write a tiny standalone preview helper
tmp_preview="$(mktemp)"
cat >"$tmp_preview" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
f="$1"
case "${f##*.}" in
  pdf|PDF)
    if command -v pdftotext >/dev/null 2>&1; then
      pdftotext -f 1 -l 2 -layout -- "$f" - 2>/dev/null | sed -n '1,80p'
    elif command -v mutool >/dev/null 2>&1; then
      mutool draw -F txt -o - -p 1-2 -- "$f" 2>/dev/null | sed -n '1,80p'
    else
      echo "(Preview not available: install pdftotext or mutool)"
    fi
    ;;
  epub|EPUB)
    echo "(EPUB preview not supported)"
    ;;
  *)
    echo "(Unknown file type)"
    ;;
esac
EOF
chmod +x "$tmp_preview"

# Run fzf with the simple preview command
selection="$(
  printf '%s\n' "${files[@]}" |
    fzf --ansi --no-multi \
      --prompt="Search: " \
      --header="Directory: $SEARCH_DIR (Enter to open)" \
      --preview="$tmp_preview {}" \
      --preview-window=right,70%,border \
      --height=85%
)"

# Clean the helper
rm -f "$tmp_preview"

# User aborted
[[ -z "${selection:-}" ]] && exit 0

# Open the selected file
ext="${selection##*.}"
case "$ext" in
pdf | PDF)
  require tdf
  exec tdf "$selection"
  ;;
epub | EPUB)
  require sioyek
  # Detach from terminal so closing the parent shell won't kill it
  setsid sioyek --new-window "$selection" >/dev/null 2>&1 &
  disown || true
  ;;
*)
  echo "Unsupported file type: $selection" >&2
  exit 1
  ;;
esac
