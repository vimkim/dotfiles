#!/usr/bin/env bash
set -euo pipefail

exec copyparty \
    -q \
    --md-no-br \
    --js-other /_copyparty_web/copyparty-render.js \
    "$@"
