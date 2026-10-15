#!/bin/bash
# Bootstrap the editable tool from primary main. Failure leaves this run-once
# script eligible to retry on the next apply; never mark a skipped install done.
set -eu
checkout="$HOME/gh/herdr-next-to-current"
retry() {
    printf 'herdr-next-to-current: %s\n' "$1" >&2
    printf 'Retry after correcting it: chezmoi apply (or: cd "%s" && just sync)\n' "$checkout" >&2
    exit 1
}
command -v git >/dev/null || retry 'install git first'
command -v uv >/dev/null || retry 'install uv first'
command -v just >/dev/null || retry 'install just first'
if [ ! -e "$checkout" ] && [ ! -L "$checkout" ]; then
    mkdir -p "$(dirname "$checkout")"
    git clone --quiet --branch main https://github.com/vimkim/herdr-next-to-current.git "$checkout" ||
        retry 'clone failed; inspect any partial checkout before retrying'
fi
[ -d "$checkout/.git" ] && [ ! -L "$checkout" ] || retry 'occupied path or linked worktree; preserved'
root="$(git -C "$checkout" rev-parse --show-toplevel)" || retry 'cannot inspect checkout'
[ "$root" = "$(cd "$checkout" && pwd -P)" ] || retry 'path is not an independent checkout'
branch="$(git -C "$checkout" symbolic-ref --quiet --short HEAD)" || retry 'detached checkout; preserved'
[ "$branch" = main ] || retry 'checkout is not on main; preserved'
origin="$(git -C "$checkout" config --get remote.origin.url)" || retry 'missing origin; preserved'
case "$origin" in
https://github.com/vimkim/herdr-next-to-current.git|git@github.com:vimkim/herdr-next-to-current.git) ;;
*) retry 'unexpected origin; preserved' ;;
esac
status="$(git -C "$checkout" status --porcelain --untracked-files=all)" || retry 'cannot inspect status'
[ -z "$status" ] || retry 'dirty checkout; preserved'
[ -f "$checkout/justfile" ] || retry 'missing justfile'
just --justfile "$checkout/justfile" --working-directory "$checkout" sync || retry 'installation failed'

# Check the interpreter uv installed, which can differ from python3 on PATH.
tool_root="$(uv tool dir)" || retry 'cannot locate the installed Python environment'
runtime_python="$tool_root/herdr-next-to-current/bin/python"
"$runtime_python" -I -c 'import curses, sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1 ||
    retry "installed runtime requires Python 3.11+ with curses; repair the interpreter at $runtime_python and reinstall"

# Herdr is optional on machines that only use the other dotfiles. Its absence
# must not undo a successful tool install or prevent the other dotfiles applying.
if ! command -v herdr >/dev/null; then
    printf '%s\n' 'herdr-next-to-current: warning: Alt+C and Alt+Shift+C need Herdr 0.9.3 (protocol 22); herdr was not found on PATH. Install compatible Herdr before using these shortcuts.' >&2
else
    herdr_version="$(herdr --version 2>/dev/null)" || herdr_version='version check failed'
    if [ "$herdr_version" != 'herdr 0.9.3' ]; then
        printf 'herdr-next-to-current: warning: Alt+C and Alt+Shift+C need a Herdr 0.9.3 server (protocol 22); installed command reports "%s". Use compatible Herdr before using these shortcuts.\n' "$herdr_version" >&2
    fi
fi
