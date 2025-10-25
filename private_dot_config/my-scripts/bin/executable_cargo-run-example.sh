#!/usr/bin/env bash
set -euo pipefail

# deps check
command -v jq >/dev/null || {
  echo "jq is required"
  exit 1
}
command -v fzf >/dev/null || {
  echo "fzf is required"
  exit 1
}

# ensure in a Cargo project/workspace
cargo metadata --no-deps >/dev/null 2>&1 || {
  echo "run inside a Cargo project"
  exit 1
}

# list all examples across the workspace: output "example<TAB>package"
examples=$(
  cargo metadata --no-deps --format-version 1 |
    jq -r '.packages[] as $p
           | $p.targets[]
           | select(.kind[] == "example")
           | "\(.name)\t\($p.name)"'
)

[ -n "$examples" ] || {
  echo "no examples found"
  exit 0
}

# pick one with fzf, showing "example (package)"
selection=$(printf '%s\n' "$examples" |
  awk -F'\t' '{printf "%s (%s)\t%s\t%s\n",$1,$2,$1,$2}' |
  fzf --prompt="cargo example> " --with-nth=1 --delimiter='\t' --ansi --no-multi --height 60% --reverse |
  cut -f2-)

# user canceled
[ -n "$selection" ] || exit 0

example_name=$(printf '%s' "$selection" | cut -f1)
package_name=$(printf '%s' "$selection" | cut -f2)

# run it, forward any extra args to the example binary
exec cargo run -p "$package_name" --example "$example_name" -- "$@"
