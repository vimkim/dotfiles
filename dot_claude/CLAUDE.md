# Global Claude Code Guidelines

## Clarify Before Acting

- If anything is ambiguous, ask me (AskUserQuestion) before proceeding. Never assume.

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

## CUBRID Local Knowledge Dirs

For any CUBRID work, check these two local directories first — they hold my own context that is often not derivable from the source tree or git history:

- `~/gh/my-cubrid-jira/` — personal JIRA issue notes in Markdown, the local source of truth per issue (`issues/CBRD-<number>[-slug].md`), uploaded to https://jira.cubrid.org. Do not hand-craft JIRA API calls to upload; use the repo's uploader scripts / `just` recipes.
- `~/gh/my-cubrid-docs/` — detailed per-issue documentation, one directory per issue (`cbrd-XXXXX/`). These are the "linked detailed doc" referenced when writing CUBRID PRs.

Before searching elsewhere or asking about a CBRD ticket, look here for existing context.
