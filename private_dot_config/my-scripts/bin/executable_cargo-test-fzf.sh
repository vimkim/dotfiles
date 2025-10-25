#!/usr/bin/env bash
set -euo pipefail

command -v jq >/dev/null || { echo "jq is required"; exit 1; }
command -v fzf >/dev/null || { echo "fzf is required"; exit 1; }
cargo metadata --no-deps >/dev/null 2>&1 || { echo "run inside a Cargo workspace"; exit 1; }

# Build once to make listing faster later
cargo test --workspace --no-run >/dev/null 2>&1 || true

# Gather tests per package: output "test_name<TAB>package"
tests=$(
  cargo metadata --no-deps --format-version 1 \
  | jq -r '.packages[].name' \
  | while read -r pkg; do
      # list tests for this package; keep only lines that end with ": test" or ": bench"
      cargo test -p "$pkg" -- --list 2>/dev/null \
      | grep -E ': (test|bench)$' \
      | sed -E 's/[[:space:]]+: (test|bench)$//' \
      | while read -r t; do printf '%s\t%s\n' "$t" "$pkg"; done
    done
)

[ -n "$tests" ] || { echo "no tests found"; exit 0; }

# Pick one with fzf, showing "test (package)"
selection=$(printf '%s\n' "$tests" \
  | awk -F'\t' '{printf "%s (%s)\t%s\t%s\n",$1,$2,$1,$2}' \
  | fzf --prompt="cargo test> " --with-nth=1 --delimiter='\t' --no-multi --height 60% --reverse \
  | cut -f2-)

[ -n "$selection" ] || exit 0

test_name=$(printf '%s' "$selection" | cut -f1)
package_name=$(printf '%s' "$selection" | cut -f2)

# Run the selected test exactly; forward extra args to libtest after --
exec cargo test -p "$package_name" "$test_name" -- --exact "$@"

