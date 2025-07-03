#!/usr/bin/env bash
ZJ_SESSIONS=$(zellij list-sessions -s)
NO_SESSIONS=$(echo "${ZJ_SESSIONS}" | wc -l)

if [ "${NO_SESSIONS}" -ge 1 ]; then
    chosen="$(echo "${ZJ_SESSIONS}" | fzf)"
    if [ -z "$chosen" ]; then
        echo "No session selected."
        exit 0
    fi
    zellij attach "$chosen"
else
    zellij -s "$(hostname)"
fi
