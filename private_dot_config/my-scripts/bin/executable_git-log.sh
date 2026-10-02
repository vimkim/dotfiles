#!/usr/bin/env bash
# Thin wrapper kept for existing callers (gl, gld, glh, zsh aliases).
# The logic lives in git-log.py next to this script; see `git-log.sh --help`.
exec python3 "$(dirname "$(readlink -f "$0")")/git-log.py" "$@"
