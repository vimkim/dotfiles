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
#   ▸ --all-branch  → our own flag: label every ref, not just the named ones
###############################################################################
GL_OPS_EXTRA=()
BRANCHES=()
ALL_LABELS=0

for arg in "$@"; do
  if [[ "$arg" == --all-branch ]]; then
    ALL_LABELS=1
  elif [[ "$arg" == -* ]]; then
    GL_OPS_EXTRA+=("$arg")
  else
    BRANCHES+=("$arg")
  fi
done

###############################################################################
# Ref labels: with named revisions, label only their refs (a raw commit gets
# the refs pointing exactly at it) plus HEAD. HEAD keeps the filter non-empty,
# since no --decorate-refs at all would label everything.
###############################################################################
DECORATE_REFS=()

if [[ ${#BRANCHES[@]} -eq 0 ]]; then
  # If the user didn’t name any branches, default to --all
  BRANCHES=(--all)
elif (( ! ALL_LABELS )); then
  DECORATE_REFS=(--decorate-refs=HEAD)
  for rev in "${BRANCHES[@]}"; do
    refs=$(git rev-parse --symbolic-full-name "$rev" 2>/dev/null | sed -n 's/^^\{0,1\}\(refs\/.*\)/\1/p' || true)
    if [[ -z $refs ]]; then
      commit=$(git rev-parse --verify --quiet "$rev^{commit}" || true)
      if [[ -n $commit ]]; then
        refs=$(git for-each-ref --points-at="$commit" --format='%(refname)')
      fi
    fi
    while IFS= read -r ref; do
      if [[ -n $ref ]]; then
        DECORATE_REFS+=("--decorate-refs=$ref")
      fi
    done <<<"$refs"
  done
fi

###############################################################################
# Finally run git-log
###############################################################################
GIT_PAGER="less -iRFSX" \
git log \
  "${GL_OPS_DEFAULT[@]}" \
  "${DECORATE_REFS[@]}" \
  "${GL_OPS_EXTRA[@]}" \
  --pretty=format:"$GIT_PRETTY_FORMAT" \
  "${BRANCHES[@]}"

