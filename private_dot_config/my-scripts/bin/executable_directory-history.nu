#!/usr/bin/env bash
# Compatibility for already-open Bash/Zsh sessions. New adapters use dir-history.
output=''
record=''
mode=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --record|--output)
            [ "$#" -ge 2 ] || { printf 'directory-history.nu: missing option value\n' >&2; exit 2; }
            if [ "$1" = --record ]; then record=$2; else output=$2; fi
            shift 2 ;;
        --forget|-f|--delete|-d|--prune|-p) mode+=("$1"); shift ;;
        *) printf 'directory-history.nu: unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
done
if [ -n "$record" ]; then
    exec dir-history record -- "$record"
fi
[ -n "$output" ] || { printf 'directory-history.nu: --output is required\n' >&2; exit 2; }
exec dir-history pick --output "$output" "${mode[@]}"
