#!/usr/bin/env bash

# Optional first arg: layout name passed to --layout when starting a new session.
LAYOUT="$1"

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
    exec zellij attach "$chosen"
else
    SESSION_NAME="$(hostname | cut -c1-4)"
    if [ -n "$LAYOUT" ]; then
        exec zellij -s "$SESSION_NAME" --layout "$LAYOUT"
    else
        exec zellij -s "$SESSION_NAME"
    fi
fi
