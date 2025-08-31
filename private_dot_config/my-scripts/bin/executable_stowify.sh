#!/usr/bin/env bash
set -euo pipefail

# stowify: move/create file(s) from $PWD (must be under $HOME) into a stow package,
# preserving the relative path from $HOME; then restow the package.
#
# Usage:
#   stowify [-d STOW_DIR] [-p PACKAGE] <path> [<path> ...]
# Defaults:
#   STOW_DIR = ~/dotfiles
#   PACKAGE  = default
#
# Example (running inside ~/.config/nvim):
#   stowify -p nvim init.lua lua/myplugin.lua
# -> creates/moves files to ~/dotfiles/nvim/.config/nvim/...
# -> runs: stow -d ~/dotfiles nvim

STOW_DIR="${STOW_DIR:-$HOME/dotfiles}"
PACKAGE="${PACKAGE:-default}"

print_usage() {
  echo "Usage: STOW_DIR=~/dotfiles PACKAGE=pkg stowify <path>..."
}

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--stow-dir) STOW_DIR="$2"; shift 2 ;;
    -p|--package)  PACKAGE="$2";  shift 2 ;;
    -h|--help)     print_usage; exit 0 ;;
    --)            shift; break ;;
    -*)
      echo "Unknown option: $1" >&2
      print_usage; exit 2 ;;
    *) break ;;
  esac
done

if [[ $# -lt 1 ]]; then
  print_usage; exit 2
fi

# Ensure we're under $HOME so we can compute a path relative to it
case "$PWD/" in
  "$HOME"/*|"$HOME"/) ;;
  *)
    echo "Error: PWD must be inside \$HOME. Current: $PWD" >&2
    exit 1
    ;;
esac

# Compute path from $HOME to current directory (might be ".")
RELDIR="${PWD#$HOME/}"
[ "$RELDIR" = "$HOME" ] && RELDIR="."
[ -z "$RELDIR" ] && RELDIR="."

PKG_DIR="$STOW_DIR/$PACKAGE"
mkdir -p "$PKG_DIR"

# Ensure stow exists
if ! command -v stow >/dev/null 2>&1; then
  echo "Error: 'stow' not found in PATH." >&2
  exit 1
fi

status=0
for INPUT in "$@"; do
  SRC="$PWD/$INPUT"

  # Destination path inside package mirrors $HOME-relative path
  if [[ "$RELDIR" = "." ]]; then
    DEST="$PKG_DIR/$INPUT"
  else
    DEST="$PKG_DIR/$RELDIR/$INPUT"
  fi
  DEST_DIR="$(dirname "$DEST")"
  mkdir -p "$DEST_DIR"

  if [[ -L "$SRC" ]]; then
    echo "Skip: $INPUT is already a symlink in target."
    continue
  fi

  if [[ -e "$SRC" ]]; then
    # If destination exists, avoid overwriting; otherwise move
    if [[ -e "$DEST" ]]; then
      echo "Error: $INPUT already exists in package: ${DEST#$PKG_DIR/}" >&2
      status=1
      continue
    fi
    mv "$SRC" "$DEST"
    echo "Moved: ${SRC#$HOME/} -> ${DEST#$STOW_DIR/}"
  else
    # Create empty file in package to be linked back
    if [[ ! -e "$DEST" ]]; then
      mkdir -p "$DEST_DIR"
      : > "$DEST"
      echo "Created: ${DEST#$STOW_DIR/}"
    else
      echo "Note: ${DEST#$STOW_DIR/} already exists; will restow."
    fi
  fi
done

echo "Stowing package '$PACKAGE' from $STOW_DIR ..."
stow -d "$STOW_DIR" "$PACKAGE" || status=$?

exit "$status"
