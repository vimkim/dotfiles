# Global Claude Code Guidelines

## GitHub PR Review Workflow

### gh api ANSI issue
`gh api` outputs ANSI color escape codes that break `jq` and `python3 json.load()`. Always handle this:

1. **Best: use `--jq` flag** (processes JSON internally, no ANSI issue):
   ```bash
   gh api repos/OWNER/REPO/pulls/123/comments --jq '.[] | {id, user: .user.login, body}'
   ```

2. **For complex processing:** strip ANSI in python:
   ```bash
   gh api <endpoint> 2>&1 | python3 -c "
   import sys, re, json
   data = re.sub(rb'\x1b\[[0-9;]*m', b'', sys.stdin.buffer.read())
   result = json.loads(data)
   # ... process result
   "
   ```

### Fetching PR review comments
```bash
gh api repos/OWNER/REPO/pulls/PR_NUMBER/comments --jq '.[] | {id, user: .user.login, path, line: .original_line, in_reply_to_id, body}'
```

### Replying to PR review comments
```bash
gh api repos/OWNER/REPO/pulls/PR_NUMBER/comments/COMMENT_ID/replies --method POST -f body="$(cat <<'EOF'
Reply text here (supports multi-line with heredoc)
EOF
)"
```

Notes:
- Use `--method POST` (not `-method`)
- Use heredoc for multi-line body
- The `/replies` endpoint creates a threaded reply under the original comment
