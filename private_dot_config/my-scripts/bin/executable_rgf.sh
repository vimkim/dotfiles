#!/usr/bin/env bash
set -euo pipefail

# Default pattern if you provide nothing
DEFAULT_QUERY='.'

# Split args into:
#   RG_OPTS: options/paths for ripgrep
#   PATS:    one or more patterns (after a literal --)
RG_OPTS=()
PATS=()
seen_ddash=0

for a in "$@"; do
    if [[ $a == "--" && $seen_ddash -eq 0 ]]; then
        seen_ddash=1
        continue
    fi
    if [[ $seen_ddash -eq 1 ]]; then
        PATS+=("$a")
    else
        RG_OPTS+=("$a")
    fi
done

# Build final rg arguments
RG_FINAL=(-nH --color=always -i) # default flags; you can add/remove defaults here

# If user supplied any opts (before --), keep them
if ((${#RG_OPTS[@]} > 0)); then
    RG_FINAL+=("${RG_OPTS[@]}")
fi

# If patterns were given after --, expand them as -e pat (OR semantics)
if ((${#PATS[@]} > 0)); then
    for p in "${PATS[@]}"; do
        RG_FINAL+=(-e "$p")
    done
else
    # Nothing provided? Use a sensible default
    RG_FINAL+=("$DEFAULT_QUERY")
fi

# rg "${RG_FINAL[@]}" \
git grep -p "${RG_FINAL[@]}" \
| fzf --ansi --no-sort --exact --delimiter=: \
  --preview 'bat --style=full --color=always --highlight-line {2} {1}' \
  --preview-window=right:60%:+{2}-15:wrap \
  --bind 'ctrl-u:preview-up,ctrl-d:preview-down,shift-up:preview-up,shift-down:preview-down,ctrl-f:preview-page-down,ctrl-b:preview-page-up,ctrl-a:preview-top,ctrl-e:preview-bottom' \
  --bind 'enter:execute(nvim +{2} -- {1})+abort'
