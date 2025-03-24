#!/bin/bash

query="$1"
file=$(fd . -H -I --type f --type l --max-depth 1 | fzf --height 60% --reverse --query="$query")
if [[ -n $file ]]; then
    $EDITOR "$file"
fi
