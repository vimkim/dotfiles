#!/usr/bin/env bash
# diff-dirs-with-git.sh
# Compare two directories (A and B) by committing A into a fresh git repo,
# then replacing it with B and committing again, so you can diff with lazygit or any git tool.

set -euo pipefail

usage() {
  cat <<EOF
Usage: $(basename "$0") [--keep] [--repo DIR] [--no-launch] <A> <B>

Positional:
  A                First directory (baseline)
  B                Second directory (to compare against A)

Options:
  --keep           Do NOT remove the temporary repo afterward (prints path).
  --repo DIR       Use an existing empty directory for the repo instead of mktemp.
  --no-launch      Do not auto-launch lazygit; just print the repo path and useful commands.
  -h, --help       Show this help.

Notes:
- Requires: git, rsync. If available: lazygit (optional).
- We set local git user.name/email if missing so commits succeed.
- The script excludes any nested .git/ folder inside A or B.
EOF
}

KEEP=0
LAUNCH=1
CUSTOM_REPO=""

while [[ $# -gt 0 ]]; do
  case "${1:-}" in
    --keep) KEEP=1; shift ;;
    --no-launch) LAUNCH=0; shift ;;
    --repo) CUSTOM_REPO="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*)
      echo "Unknown option: $1" >&2
      usage; exit 2 ;;
    *) break ;;
  esac
done

if [[ $# -ne 2 ]]; then
  usage; exit 2
fi

DIR_A="$1"
DIR_B="$2"

# Validate inputs
for d in "$DIR_A" "$DIR_B"; do
  if [[ ! -d "$d" ]]; then
    echo "Error: '$d' is not a directory" >&2
    exit 1
  fi
done

# Prepare repo dir
cleanup() {
  if [[ $KEEP -eq 0 && -n "${REPO_DIR:-}" && -d "$REPO_DIR" ]]; then
    rm -rf -- "$REPO_DIR"
  fi
}
trap cleanup EXIT

if [[ -n "$CUSTOM_REPO" ]]; then
  REPO_DIR="$CUSTOM_REPO"
  if [[ -e "$REPO_DIR" && -n "$(ls -A "$REPO_DIR" 2>/dev/null || true)" ]]; then
    echo "Error: --repo DIR must be empty or non-existent: $REPO_DIR" >&2
    exit 1
  fi
  mkdir -p "$REPO_DIR"
else
  REPO_DIR="$(mktemp -d -t diffdirs-XXXXXXXX)"
fi

# Init repo
git -C "$REPO_DIR" init -q
# Avoid ambiguous default branch on older/newer git versions
if git -C "$REPO_DIR" symbolic-ref -q HEAD >/dev/null 2>&1; then
  : # already has branch
else
  git -C "$REPO_DIR" checkout -q -b main
fi

# Ensure committer identity (local only)
if ! git -C "$REPO_DIR" config user.name >/dev/null; then
  git -C "$REPO_DIR" config user.name "dir-diff"
fi
if ! git -C "$REPO_DIR" config user.email >/dev/null; then
  git -C "$REPO_DIR" config user.email "dir-diff@example.invalid"
fi

# Helper: rsync copy excluding .git
copy_in() {
  local src="$1"
  local dst="$2"
  rsync -a --delete \
    --exclude=".git/" \
    --exclude=".git" \
    "$src"/ "$dst"/
}

# Commit A
copy_in "$DIR_A" "$REPO_DIR"
git -C "$REPO_DIR" add -A
git -C "$REPO_DIR" commit -q -m "Snapshot: A -> $(realpath "$DIR_A")"
git -C "$REPO_DIR" tag -f A-snapshot >/dev/null

# Replace with B and commit
copy_in "$DIR_B" "$REPO_DIR"
git -C "$REPO_DIR" add -A
git -C "$REPO_DIR" commit -q -m "Snapshot: B -> $(realpath "$DIR_B")"
git -C "$REPO_DIR" tag -f B-snapshot >/dev/null

echo "Temporary repo ready at: $REPO_DIR"
echo
echo "Quick diff commands:"
echo "  git -C \"$REPO_DIR\" diff A-snapshot..B-snapshot"
echo "  git -C \"$REPO_DIR\" difftool A-snapshot..B-snapshot     # if you have a difftool configured"
echo "  git -C \"$REPO_DIR\" log --oneline --decorate --graph    # overview"

# Launch UI if requested and available
if [[ $LAUNCH -eq 1 ]]; then
  if command -v lazygit >/dev/null 2>&1; then
    echo
    echo "Launching lazygit in: $REPO_DIR"
    (cd "$REPO_DIR" && lazygit)
  else
    echo
    echo "lazygit not found. You can open the repo in your editor:"
    echo "  cd \"$REPO_DIR\" && \$EDITOR ."
  fi
fi

# Keep or cleanup handled by trap
if [[ $KEEP -eq 1 ]]; then
  echo
  echo "Repo preserved at: $REPO_DIR"
fi

