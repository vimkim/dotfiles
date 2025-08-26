#!/usr/bin/env bash

ZJ_SESSIONS=$(zellij list-sessions -s)

if [ -z "${ZJ_SESSIONS}" ]; then
    NO_SESSIONS=0
else
    NO_SESSIONS=$(printf "%s\n" "${ZJ_SESSIONS}" | wc -l)
fi

echo "${NO_SESSIONS} sessions found."

if [ "${NO_SESSIONS}" -ge 1 ]; then
    chosen="$(printf "%s\n" "${ZJ_SESSIONS}" | fzf)"
    if [ -z "$chosen" ]; then
        echo "No session selected."
        exit 0
    fi
    zellij attach "$chosen"
else
    zellij -s "$(hostname | cut -c1-4)"
fi
