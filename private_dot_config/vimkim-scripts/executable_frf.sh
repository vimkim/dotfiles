#!/bin/bash

# Check if an fd pattern is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <fd_pattern> [rg_pattern]"
  echo "<fd_pattern>: Pattern for fd to search files"
  echo "[rg_pattern]: (Optional) Pattern for rg to search within the files"
  exit 1
fi

# Store the pattern argument
fd_pattern="$1"
rg_pattern="${2:-.}"

# Use fd to find files matching the pattern, then search with rg
fd "$fd_pattern" -t f | xargs rg "$rg_pattern" --column --line-number --no-heading --color=always --smart-case |
  fzf --ansi --delimiter : \
    --preview 'bat --color=always {1} --highlight-line {2}' --preview-window 'up,60%,border-bottom,+{2}+3/3,~3' \
    --bind "enter:become($EDITOR {1} +{2})"

# fd '$@' -t f | xargs rg 'install' --column --line-number --no-heading --color=always --smart-case | fzf --ansi --delimiter : --preview 'bat --color=always {1} --highlight-line {2}' --preview-window 'up,60%,border-bottom,+{2}+3/3,~3'
