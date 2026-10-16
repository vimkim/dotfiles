#!/bin/bash
# Install before applying the legacy asset directory's compatibility symlink.
set -eu
checkout="$HOME/gh/html-serve"
retry() {
    printf 'html-serve: %s\n' "$1" >&2
    printf 'Retry: bash "%s/.chezmoiscripts/run_once_before_install-html-serve.sh"\n' "$(chezmoi source-path)" >&2
    exit 1
}
command -v git >/dev/null || retry 'install git first'
command -v uv >/dev/null || retry 'install uv first'
command -v just >/dev/null || retry 'install just first'
command -v python3 >/dev/null || retry 'install python3 first'
command -v chezmoi >/dev/null || retry 'install chezmoi first'
if [ ! -e "$checkout" ] && [ ! -L "$checkout" ]; then
    mkdir -p "$(dirname "$checkout")"
    git clone --quiet --branch main https://github.com/vimkim/html-serve.git "$checkout" ||
        retry 'clone failed; inspect any partial checkout before retrying'
fi
[ -d "$checkout/.git" ] && [ ! -L "$checkout" ] || retry 'occupied path or linked worktree; preserved'
root="$(git -C "$checkout" rev-parse --show-toplevel)" || retry 'cannot inspect checkout'
[ "$root" = "$(cd "$checkout" && pwd -P)" ] || retry 'path is not an independent checkout'
branch="$(git -C "$checkout" symbolic-ref --quiet --short HEAD)" || retry 'detached checkout; preserved'
[ "$branch" = main ] || retry 'checkout is not on main; preserved'
origin="$(git -C "$checkout" config --get remote.origin.url)" || retry 'missing origin; preserved'
case "$origin" in
https://github.com/vimkim/html-serve.git|git@github.com:vimkim/html-serve.git) ;;
*) retry 'unexpected origin; preserved' ;;
esac
status="$(git -C "$checkout" status --porcelain --untracked-files=all)" || retry 'cannot inspect status'
[ -z "$status" ] || retry 'dirty checkout; preserved'
[ -f "$checkout/justfile" ] || retry 'missing justfile'
just --justfile "$checkout/justfile" --working-directory "$checkout" sync || retry 'installation failed'

# Preserve local changes and retain an exact legacy installation as a backup.
# Chezmoi's helper applies the symlink after this script vacates the old path.
python3 - "$checkout/src/html_serve/assets" <<'PY'
from pathlib import Path
import os
import subprocess
import sys

assets = Path(sys.argv[1])
legacy = Path.home() / ".config/my-scripts/share/serve-html"
backup = Path.home() / ".local/state/html-serve/legacy-assets"
if legacy.is_symlink():
    if legacy.resolve() != assets.resolve():
        print(f"html-serve: preserved unexpected legacy asset symlink: {legacy}")
    sys.exit(0)
if not legacy.exists():
    sys.exit(0)
if os.environ.get("CHEZMOI") == "1":
    sys.exit("html-serve: legacy asset directory preserved. Run the bootstrap script "
             "directly before chezmoi-apply-unmodified; a parent chezmoi apply "
             "holds the state lock needed for this one-time migration.")

def inventory(directory):
    if not directory.is_dir():
        return None
    result = {}
    for child in directory.rglob("*"):
        if child.is_symlink() or not (child.is_file() or child.is_dir()):
            return None
        result[child.relative_to(directory)] = child.read_bytes() if child.is_file() else None
    return result

expected = inventory(assets)
if expected is None or inventory(legacy) != expected:
    print(f"html-serve: preserved locally changed legacy assets: {legacy}")
elif backup.exists() or backup.is_symlink():
    print(f"html-serve: preserved legacy assets; backup path already exists: {backup}")
else:
    backup.parent.mkdir(parents=True, exist_ok=True)
    os.rename(legacy, backup)
    try:
        # Forget the directory's old state so the helper sees a new symlink,
        # rather than interpreting this verified move as a local deletion.
        subprocess.run(["chezmoi", "state", "delete", "--bucket=entryState",
                        "--key=" + str(legacy)], check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        if not legacy.exists() and not legacy.is_symlink():
            os.rename(backup, legacy)
        raise
    print(f"html-serve: backed up unchanged legacy assets: {backup}")
PY
