# Global Claude Code Guidelines

## GitHub PR Review Workflow

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

## CUBRID JIRA

- CUBRID JIRA: http://jira.cubrid.org/browse/CBRD-XXXXX (public, no auth)
- REST API: `http://jira.cubrid.org/rest/api/2/issue/CBRD-XXXXX`
- Use `/jira CBRD-XXXXX` to fetch full issue context (description, comments, linked issues) with pandoc jira→markdown conversion
- When a user mentions a CBRD-XXXXX ticket, use `/jira` to look it up rather than asking the user to explain
