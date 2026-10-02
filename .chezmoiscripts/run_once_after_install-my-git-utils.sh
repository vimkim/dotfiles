#!/bin/bash
# Bootstrap vimkim/my-git-utils (git-log, git-log-pick, git-log-pr) on a fresh
# machine. Idempotent and never fails chezmoi: it only clones a missing
# checkout, and leaves an existing one to daily-update.
set -u
dir="$HOME/gh/my-git-utils"

if [ ! -d "$dir/.git" ]; then
    mkdir -p "$(dirname "$dir")"
    git clone --quiet https://github.com/vimkim/my-git-utils.git "$dir" || {
        echo "my-git-utils: clone failed; retry: git clone https://github.com/vimkim/my-git-utils.git $dir" >&2
        exit 0
    }
fi

if ! command -v uv >/dev/null || ! command -v just >/dev/null; then
    echo "my-git-utils: install uv and just, then run: just --justfile $dir/justfile --working-directory $dir sync" >&2
    exit 0
fi

just --justfile "$dir/justfile" --working-directory "$dir" sync ||
    echo "my-git-utils: install failed; retry: just --justfile $dir/justfile --working-directory $dir sync" >&2
exit 0
