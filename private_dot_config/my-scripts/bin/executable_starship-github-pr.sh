#!/usr/bin/env bash
# Print the current branch's open GitHub PR number, for the starship prompt.
# Never blocks the prompt on the network: the cached value is printed
# immediately, and a stale/missing entry is refreshed in the background
# (visible from the next prompt onward).
set -u

branch=$(git branch --show-current 2>/dev/null)
[ -n "$branch" ] || exit 0
repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
[ -n "$repo_root" ] || exit 0

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/starship-github-pr"
mkdir -p "$cache_dir"
cache="$cache_dir/$(printf '%s' "$repo_root@$branch" | md5sum | awk '{print $1}')"

ttl=600
now=$(date +%s)
mtime=$(stat -c %Y "$cache" 2>/dev/null || echo 0)

if [ $((now - mtime)) -ge $ttl ]; then
  (
    cd "$repo_root" || exit 0
    # An empty file is a valid cache entry meaning "no open PR" — it stops
    # us from re-querying the API on every prompt until the TTL expires.
    gh pr view --json number,state \
      --jq 'select(.state == "OPEN") | .number' \
      2>/dev/null >"$cache.tmp.$$"
    mv "$cache.tmp.$$" "$cache"
  ) >/dev/null 2>&1 &
fi

[ -f "$cache" ] && cat "$cache"
exit 0
