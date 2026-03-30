---
name: jira
description: Look up CUBRID JIRA issue context. Use when a CBRD-XXXXX ticket is mentioned or when the user asks about a JIRA issue.
argument-hint: <CBRD-XXXXX>
---

Look up CUBRID JIRA issue context.

Given a JIRA ticket ID (e.g., CBRD-25123), fetch the issue details from the CUBRID JIRA REST API and present a comprehensive summary. The argument is the ticket ID.

If no ticket ID is provided, ask for one.

$ARGUMENTS

Steps:
1. First, check if a local issue file exists in `~/gh/my-cubrid-jira/issues/` by looking for files matching the ticket ID prefix (e.g., `CBRD-26609*.md`). Use the Glob tool with pattern `CBRD-XXXXX*.md` in path `/home/vimkim/gh/my-cubrid-jira/issues/`.

2. **If a local file is found**: Read it with the Read tool and present its contents to the user. Skip the fetch step entirely.

3. **If no local file is found**: Use the Bash tool to run:

```
python3 ${CLAUDE_SKILL_DIR}/scripts/jira_fetch.py TICKET_ID
```

4. Present the output to the user as-is. The script formats everything into readable markdown with JIRA wiki markup converted via pandoc.
5. If the command fails, inform the user that the JIRA instance may be unreachable.
