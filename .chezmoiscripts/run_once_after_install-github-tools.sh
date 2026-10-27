#!/bin/bash
# Deploy the shared implementation first. Failed installs retry on the next apply.
set -eu
scripts="${XDG_CONFIG_HOME:-$HOME/.config}/my-scripts"
exec python3 -B - "$scripts" <<'PY'
import sys

if sys.version_info < (3, 11):
    sys.exit("GitHub tools require Python 3.11 or newer")
sys.path.insert(0, sys.argv[1])
from daily_update.github import bootstrap

sys.exit(bootstrap())
PY
