#!/usr/bin/env bash

export FORCE_COLOR=1

# Create a function to get logo names
get_logo_names() {
    fastfetch --list-logos | while read -r line; do
        [[ -z "$line" ]] && continue
        if [[ $line =~ \"([^\"]+)\" ]]; then
            echo "${BASH_REMATCH[1]}"
        fi
    done
}

# Pipe the output directly to fzf
get_logo_names | fzf \
    --preview 'TERM=xterm-256color FORCE_COLOR=1 fastfetch -l {} --pipe false' \
    --preview-window=right:70% \
    --color \
    --ansi \
    --height=100% \
    --bind='ctrl-r:reload(get_logo_names)' \
    --header='Press ctrl-r to reload logo list, enter to select, esc to quit'
