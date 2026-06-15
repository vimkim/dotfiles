#!/usr/bin/env bash
# lazygit-ai-commit.sh
#
# Generate a Conventional Commits message from the staged diff using Claude
# Code (headless `claude -p`), open it in $EDITOR for review, then commit.
#
# Bound to "C" in lazygit (~/.config/lazygit/config.yml, customCommands).
# It lives as a standalone script because lazygit runs custom commands through
# the login shell (nushell here), and nushell rejects bash's `&&` and `>`
# operators. A shebang'd script is run by the kernel under bash regardless of
# the calling shell, sidestepping that entirely.
set -euo pipefail

# Nothing staged? Bail early with a clear message instead of asking the model
# to describe an empty diff.
if git diff --staged --quiet; then
  echo "Nothing staged — stage changes first, then press C." >&2
  exit 1
fi

msg_file="$(mktemp -t lazygit-ai-commit.XXXXXX)"
trap 'rm -f "$msg_file"' EXIT

git diff --staged | claude -p 'Write a Conventional Commits message for the staged diff. Format: type(scope): subject — e.g. docs(cbrd-26668): summarize the change. Output ONLY the raw commit message: no markdown, no code fences, no explanation. Keep the subject under 72 chars; add a short body only if it genuinely adds value.' \
  --model haiku --output-format text >"$msg_file"

# Empty model output? Don't open an editor on nothing.
if [ ! -s "$msg_file" ]; then
  echo "Claude returned an empty message — aborting." >&2
  exit 1
fi

# -F seeds the message from the file; -e forces the editor open anyway so you
# review/edit before the commit is created. Quit without saving to abort.
git commit -e -F "$msg_file"
