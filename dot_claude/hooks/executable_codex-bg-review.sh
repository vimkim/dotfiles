#!/usr/bin/env bash
# Fire-and-forget background Codex review on Stop.
# Layered on top of the synchronous stop-review gate enabled via
# /codex:setup --enable-review-gate. Always returns immediately so it
# does not block the Stop event.

set -u

PLUGIN_DIR="$HOME/.claude/plugins/cache/openai-codex/codex"
[ -d "$PLUGIN_DIR" ] || exit 0

LATEST="$(ls -1 "$PLUGIN_DIR" 2>/dev/null | sort -V | tail -n1)"
[ -n "$LATEST" ] || exit 0

SCRIPT="$PLUGIN_DIR/$LATEST/scripts/codex-companion.mjs"
[ -f "$SCRIPT" ] || exit 0

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

LOG_DIR="$HOME/.claude/logs"
mkdir -p "$LOG_DIR"

setsid nohup node "$SCRIPT" review --background \
  >>"$LOG_DIR/codex-bg-review.log" 2>&1 </dev/null &
disown
exit 0
