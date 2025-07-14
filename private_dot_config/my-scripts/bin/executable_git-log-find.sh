#!/usr/bin/env bash
# glp  — git-log for branches whose names contain given substrings
# Example:  glp cubvec dev -n 40 --since=1.month

set -euo pipefail

###############################################################################
# Pretty format (same as gl)
###############################################################################
GIT_PRETTY_FORMAT='%C(auto)%h %C(magenta)%as%C(reset) %C(blue)%an%C(reset)%C(auto)%d %s %C(black)%C(bold)%cr%C(reset)'

###############################################################################
# Options we always want
###############################################################################
GL_OPS_DEFAULT=(--graph --oneline --color --decorate --date-order)

###############################################################################
# Separate CLI args →  GL_OPS_EXTRA (begins with ‘-’)  vs  PATTERNS (everything else)
###############################################################################
GL_OPS_EXTRA=()
PATTERNS=()

for arg in "$@"; do
  if [[ $arg == -* ]]; then
    GL_OPS_EXTRA+=("$arg")
  else
    PATTERNS+=("$arg")
  fi
done

###############################################################################
# If no patterns, fall back to --all  (same behaviour as gl)
###############################################################################
if [[ ${#PATTERNS[@]} -eq 0 ]]; then
  BRANCHES=(--all)
else
  # Get **local + remote** branch names
  mapfile -t ALL_BRANCHES < <(
    git for-each-ref --format='%(refname:short)' refs/heads refs/remotes \
    | sort -u
  )

  # Pick ones whose names contain *any* of the given substrings
  BRANCHES=()
  for b in "${ALL_BRANCHES[@]}"; do
    for pat in "${PATTERNS[@]}"; do
      if [[ $b == *"$pat"* ]]; then
        BRANCHES+=("$b")
        break               # don’t add the same branch twice
      fi
    done
  done

  # Nothing matched?  Bail out gracefully.
  if [[ ${#BRANCHES[@]} -eq 0 ]]; then
    echo "glp: no branches matched: ${PATTERNS[*]}" >&2
    exit 1
  fi
fi

###############################################################################
# Show the log
###############################################################################
GIT_PAGER="less -iRFSX" \
git log \
  "${GL_OPS_DEFAULT[@]}" \
  "${GL_OPS_EXTRA[@]}" \
  --pretty=format:"$GIT_PRETTY_FORMAT" \
  "${BRANCHES[@]}"

