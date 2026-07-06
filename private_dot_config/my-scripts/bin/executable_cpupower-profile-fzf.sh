#!/usr/bin/env bash
set -euo pipefail

require() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf '%s is required\n' "$1" >&2
        exit 1
    fi
}

available_governors() {
    local governor_file

    for governor_file in /sys/devices/system/cpu/cpu*/cpufreq/scaling_available_governors; do
        if [[ -r "$governor_file" ]]; then
            tr ' ' '\n' <"$governor_file"
            return 0
        fi
    done

    cpupower frequency-info -g 2>/dev/null |
        sed -n 's/.*available cpufreq governors: //p' |
        tr ' ' '\n'
}

current_governor() {
    local governor_file

    for governor_file in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        if [[ -r "$governor_file" ]]; then
            cat "$governor_file"
            return 0
        fi
    done

    cpupower frequency-info -p 2>/dev/null |
        sed -n 's/.*The governor "\([^"]*\)".*/\1/p' |
        head -n 1
}

require cpupower
require fzf

profiles="$(available_governors | awk 'NF' | sort -u)"

if [[ -z "$profiles" ]]; then
    printf 'No cpupower governors found.\n' >&2
    exit 1
fi

current="$(current_governor || true)"
header="Select cpupower governor"
if [[ -n "$current" ]]; then
    header+=" (current: $current)"
fi

selected="$(
    printf '%s\n' "$profiles" |
        awk -v current="$current" '
            $0 == current { print $0 "\tcurrent"; next }
            { print }
        ' |
        fzf --prompt='cpupower profile> ' \
            --header="$header" \
            --height 40% \
            --reverse \
            --no-multi \
            --delimiter='\t' \
            --with-nth=1,2
)" || exit 0

governor="${selected%%$'\t'*}"

if [[ -z "$governor" ]]; then
    exit 0
fi

if [[ "$governor" == "$current" ]]; then
    printf 'cpupower governor already set to %s\n' "$governor"
    exit 0
fi

sudo cpupower frequency-set -g "$governor"
