#!/usr/bin/env bash

# Optional first arg: layout name passed to --layout when starting a new session.
LAYOUT="$1"

ZJ_SESSIONS=$(zellij list-sessions -s 2>/dev/null)

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

    # No layout passed explicitly (plain `za`): fuzzy-pick one from
    # ~/.config/zellij/layouts, mirroring the zs/zn pickers in zellij.nu.
    # `zv` passes a layout ("vtabs") so it skips the picker.
    if [ -z "$LAYOUT" ]; then
        LAYOUT_DIR="${HOME}/.config/zellij/layouts"
        LAYOUTS="$(find "$LAYOUT_DIR" -maxdepth 1 -name '*.kdl' -exec basename {} .kdl \; 2>/dev/null | sort)"
        if [ -n "$LAYOUTS" ]; then
            LAYOUT="$(printf "%s\n" "$LAYOUTS" | fzf --height 60% --reverse --header "Select layout for new zellij session")"
            if [ -z "$LAYOUT" ]; then
                echo "No layout selected."
                exit 0
            fi
        fi
    fi

    if [ -n "$LAYOUT" ]; then
        # Use -n/--new-session-with-layout, NOT --layout: with -s/--session,
        # --layout means "add these tabs to that (existing) session" and aborts
        # with "There is no active session!" since the session is brand new.
        exec zellij -s "$SESSION_NAME" --new-session-with-layout "$LAYOUT"
    else
        exec zellij -s "$SESSION_NAME"
    fi
fi
