#!/usr/bin/env bash
set -euo pipefail

index_root="${XDG_CONFIG_HOME:-${HOME}/.config}/copyparty/index"

exec python3 -m http.server 8080 --bind 0.0.0.0 --directory "${index_root}"
