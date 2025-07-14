#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Pretty format
###############################################################################
GIT_PRETTY_FORMAT='%C(auto)%h %C(magenta)%as%C(reset) %C(blue)%an%C(reset)%C(auto)%d %s %C(black)%C(bold)%cr%C(reset)'

###############################################################################
# Default options we always want
###############################################################################
GL_OPS_DEFAULT=(--graph --oneline --color --decorate --date-order)

###############################################################################
# Split the user’s argv into
#   ▸ GL_OPS_EXTRA  → git-log options beginning with ‘-’ (e.g. -n 30, --since=2.weeks)
#   ▸ BRANCHES      → anything else (treated as revision/branch names)
###############################################################################
GL_OPS_EXTRA=()
BRANCHES=()

for arg in "$@"; do
  if [[ "$arg" == -* ]]; then
    GL_OPS_EXTRA+=("$arg")
  else
    BRANCHES+=("$arg")
  fi
done

# If the user didn’t name any branches, default to --all
[[ ${#BRANCHES[@]} -eq 0 ]] && BRANCHES=(--all)

###############################################################################
# Finally run git-log
###############################################################################
GIT_PAGER="less -iRFSX" \
git log \
  "${GL_OPS_DEFAULT[@]}" \
  "${GL_OPS_EXTRA[@]}" \
  --pretty=format:"$GIT_PRETTY_FORMAT" \
  "${BRANCHES[@]}"

