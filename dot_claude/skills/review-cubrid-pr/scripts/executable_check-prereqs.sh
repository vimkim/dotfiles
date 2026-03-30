#!/usr/bin/env bash
# check-prereqs.sh — Validate prerequisites for CUBRID PR review
#
# Checks:
#   1. PR URL format (https://github.com/OWNER/REPO/pull/NUMBER)
#   2. Inside a git repository
#   3. compile_commands.json exists (built with `just build`)
#   4. PR is open on GitHub
#   5. Local HEAD matches the PR's head SHA
#
# On success: prints JSON metadata to stdout
# On failure: prints FAIL message to stderr and exits non-zero

set -euo pipefail

PR_URL="${1:-}"

# --- Validate PR URL ---
if [[ -z "$PR_URL" ]]; then
  echo "FAIL: No PR URL provided." >&2
  echo "Usage: /review-cubrid-pr https://github.com/CUBRID/cubrid/pull/6930" >&2
  exit 1
fi

if [[ ! "$PR_URL" =~ ^https://github\.com/([^/]+)/([^/]+)/pull/([0-9]+)$ ]]; then
  echo "FAIL: Invalid PR URL format: $PR_URL" >&2
  echo "Expected: https://github.com/OWNER/REPO/pull/NUMBER" >&2
  exit 1
fi

OWNER="${BASH_REMATCH[1]}"
REPO="${BASH_REMATCH[2]}"
PR_NUMBER="${BASH_REMATCH[3]}"

# --- Check git repository ---
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
  echo "FAIL: Not inside a git repository. Run from a CUBRID clone." >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"

# --- Check compile_commands.json ---
if [[ ! -f "$REPO_ROOT/compile_commands.json" ]]; then
  echo "FAIL: compile_commands.json not found at $REPO_ROOT/" >&2
  echo "Build first with: just build" >&2
  exit 1
fi

# --- Fetch PR metadata ---
PR_JSON=$(gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER" 2>&1) || {
  echo "FAIL: Could not fetch PR #$PR_NUMBER from $OWNER/$REPO" >&2
  echo "$PR_JSON" >&2
  exit 1
}

PR_HEAD_SHA=$(echo "$PR_JSON" | jq -r '.head.sha')
PR_BASE_REF=$(echo "$PR_JSON" | jq -r '.base.ref')
PR_STATE=$(echo "$PR_JSON" | jq -r '.state')
PR_TITLE=$(echo "$PR_JSON" | jq -r '.title')
PR_DRAFT=$(echo "$PR_JSON" | jq -r '.draft')
PR_AUTHOR=$(echo "$PR_JSON" | jq -r '.user.login')
PR_BODY=$(echo "$PR_JSON" | jq -r '.body // ""')

# --- Check PR is open ---
if [[ "$PR_STATE" != "open" ]]; then
  echo "FAIL: PR #$PR_NUMBER is '$PR_STATE' (expected 'open')." >&2
  exit 1
fi

# --- Check local HEAD matches PR head ---
LOCAL_HEAD=$(git rev-parse HEAD)
if [[ "$LOCAL_HEAD" != "$PR_HEAD_SHA" ]]; then
  echo "FAIL: Local HEAD does not match PR head." >&2
  echo "  Local:  $LOCAL_HEAD" >&2
  echo "  PR:     $PR_HEAD_SHA" >&2
  echo "" >&2
  echo "Checkout the PR first:" >&2
  echo "  gh pr checkout $PR_NUMBER" >&2
  exit 1
fi

# --- All checks passed — output metadata as JSON ---
jq -n \
  --arg owner "$OWNER" \
  --arg repo "$REPO" \
  --arg number "$PR_NUMBER" \
  --arg head_sha "$PR_HEAD_SHA" \
  --arg base_ref "$PR_BASE_REF" \
  --arg state "$PR_STATE" \
  --arg title "$PR_TITLE" \
  --arg draft "$PR_DRAFT" \
  --arg author "$PR_AUTHOR" \
  --arg body "$PR_BODY" \
  --arg repo_root "$REPO_ROOT" \
  --arg pr_url "$PR_URL" \
  '{
    status: "OK",
    owner: $owner,
    repo: $repo,
    number: ($number | tonumber),
    pr_url: $pr_url,
    head_sha: $head_sha,
    base_ref: $base_ref,
    state: $state,
    title: $title,
    draft: ($draft == "true"),
    author: $author,
    body: $body,
    repo_root: $repo_root
  }'
