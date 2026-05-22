#!/usr/bin/env bash
# Daily GitHub PR focus-state digest -> writes to ~/.cache/pr-digest.md
# nushell startup hook shows it once per day on first shell.
# Wired to ~/.config/systemd/user/pr-digest.{service,timer}.
set -euo pipefail

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}"
OUT="$CACHE_DIR/pr-digest.md"
TMP="$OUT.tmp"

mkdir -p "$CACHE_DIR"

QUERY='{ viewer { pullRequests(first: 50, states: OPEN, orderBy: {field: UPDATED_AT, direction: DESC}) { nodes { number title isDraft reviewDecision repository { nameWithOwner } url } } } }'

if ! response=$(gh api graphql -f query="$QUERY" 2>&1); then
  printf '## GitHub PR digest failed\n\n%s\n' "$response" > "$TMP"
  mv "$TMP" "$OUT"
  exit 1
fi

# Build the digest. jq emits the whole formatted block including counts header.
printf '%s' "$response" | jq -r '
  .data.viewer.pullRequests.nodes as $all
  | ($all | map(select(.isDraft))) as $drafts
  | ($all | map(select(.isDraft | not))) as $live
  | ($live | map(select(.reviewDecision == "APPROVED"))) as $approved
  | ($live | map(select(.reviewDecision == "CHANGES_REQUESTED"))) as $changes
  | ($live | map(select(.reviewDecision == "REVIEW_REQUIRED"))) as $review
  | ($live | map(select(.reviewDecision == null))) as $pending
  | "============= GitHub PR Focus =============="
  , (if ($approved | length) > 0 then "✓ \($approved | length) APPROVED  (ready to merge)" else "✓ 0 APPROVED" end)
  , (if ($changes  | length) > 0 then "⚠ \($changes  | length) changes requested" else "⚠ 0 changes requested" end)
  , "… \($review  | length) awaiting review"
  , "· \($pending | length) pending (no decision yet)"
  , "✎ \($drafts  | length) drafts"
  , ""
  , (if ($approved | length) > 0 then
        ("READY TO MERGE:\n" + ($approved | map("  \(.repository.nameWithOwner)#\(.number) — \(.title)") | join("\n")) + "\n")
     else empty end)
  , (if ($changes | length) > 0 then
        ("NEEDS YOUR FIXES:\n" + ($changes | map("  \(.repository.nameWithOwner)#\(.number) — \(.title)") | join("\n")) + "\n")
     else empty end)
  , "Run `ghpd` for the full table."
  , "============================================"
' > "$TMP"

mv "$TMP" "$OUT"
