#!/usr/bin/env bash
# Add user-created Claude Code skills to chezmoi.
# Excludes: symlinks (find-skills/gstack installed), omc dirs, hidden dirs.

set -euo pipefail

SKILLS_DIR="$HOME/.claude/skills"

for entry in "$SKILLS_DIR"/* "$SKILLS_DIR"/.*; do
  name="$(basename "$entry")"

  # Skip symlinks (find-skills / gstack installed)
  [[ -L "$entry" ]] && continue

  # Skip hidden entries (., .., .omc, etc.)
  [[ "$name" == .* ]] && continue

  # Skip omc dirs
  [[ "$name" == omc-* ]] && continue

  # Skip this script itself
  [[ "$name" == chezmoi-add-skills.sh ]] && continue

  echo "Adding: $entry"
  chezmoi add "$entry"
done

echo "Done."
