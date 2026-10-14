#!/usr/bin/env bash
set -euo pipefail

readonly fortivpn_project='/mnt/c/Users/vimkim/temp/my-fortivpn'

if [[ ! -f "${fortivpn_project}/justfile" ]]; then
    printf 'FortiVPN launcher project not found: %s\n' "${fortivpn_project}" >&2
    exit 1
fi

if ! command -v mise.exe >/dev/null 2>&1; then
    printf '%s\n' 'Windows mise.exe was not found on PATH.' >&2
    exit 127
fi

cd "${fortivpn_project}"
exec mise.exe exec -- just "$@"
