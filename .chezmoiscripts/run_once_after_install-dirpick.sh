#!/bin/bash
# Files are deployed before after-scripts. A failure remains retryable on apply.
set -eu
installer="$HOME/.config/my-scripts/bin/install-dirpick"
if [ ! -x "$installer" ]; then
    printf 'dirpick: missing installer at %s; deploy it and retry chezmoi apply\n' "$installer" >&2
    exit 1
fi
exec "$installer"
