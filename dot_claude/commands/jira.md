Look up CUBRID JIRA issue context.

Given a JIRA ticket ID (e.g., CBRD-25123), read the corresponding file from `/home/vimkim/gh/my-cubrid-jira/issues/` to get the issue context. The argument is the ticket ID.

If no ticket ID is provided, ask for one.

Steps:
1. Search for files matching the ticket ID in `/home/vimkim/gh/my-cubrid-jira/issues/`
2. Read the matching file(s)
3. Summarize the issue: title, status, description, and key details

$ARGUMENTS
