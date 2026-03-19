Look up CUBRID JIRA issue context.

Given a JIRA ticket ID (e.g., CBRD-25123), fetch the issue details from the CUBRID JIRA REST API and present a comprehensive summary. The argument is the ticket ID.

If no ticket ID is provided, ask for one.

Steps:
1. First, check if a local issue file exists in `~/gh/my-cubrid-jira/issues/` by looking for files matching the ticket ID prefix (e.g., `CBRD-26609*.md`). Use the Glob tool with pattern `CBRD-XXXXX*.md` in path `/home/vimkim/gh/my-cubrid-jira/issues/`.

2. **If a local file is found**: Read it with the Read tool and present its contents to the user. Skip the curl step entirely.

3. **If no local file is found**: Use the Bash tool to run the following curl command, replacing TICKET_ID with the provided ticket ID:

```
curl -sL "http://jira.cubrid.org/rest/api/2/issue/TICKET_ID?fields=summary,status,priority,assignee,reporter,description,comment,issuelinks,fixVersions,versions,issuetype,parent,labels,created,updated,resolution,components" | python3 -c "
import json, sys, subprocess

def jira_to_md(text):
    if not text:
        return ''
    result = subprocess.run(['pandoc', '-f', 'jira', '-t', 'gfm', '--wrap=none'],
                            input=text, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else text

data = json.load(sys.stdin)
f = data['fields']

print('# ' + data['key'] + ': ' + (f.get('summary') or ''))
print()
print('| Field | Value |')
print('|-------|-------|')
print('| Type |', (f.get('issuetype') or {}).get('name', 'N/A'), '|')
print('| Status |', (f.get('status') or {}).get('name', 'N/A'), '|')
print('| Priority |', (f.get('priority') or {}).get('name', 'N/A'), '|')
print('| Assignee |', (f.get('assignee') or {}).get('displayName', 'Unassigned'), '|')
print('| Reporter |', (f.get('reporter') or {}).get('displayName', 'N/A'), '|')
print('| Created |', (f.get('created') or 'N/A')[:10], '|')
print('| Updated |', (f.get('updated') or 'N/A')[:10], '|')
print('| Resolution |', (f.get('resolution') or {}).get('name', 'Unresolved') if f.get('resolution') else 'Unresolved', '|')
if f.get('parent'):
    print('| Parent |', f['parent']['key'] + ': ' + f['parent']['fields']['summary'], '|')
if f.get('fixVersions'):
    print('| Fix Version |', ', '.join(v['name'] for v in f['fixVersions']), '|')
if f.get('versions'):
    print('| Affects Version |', ', '.join(v['name'] for v in f['versions']), '|')
if f.get('labels'):
    print('| Labels |', ', '.join(f['labels']), '|')
if f.get('components'):
    print('| Components |', ', '.join(c['name'] for c in f['components']), '|')

print()
print('## Description')
print()
print(jira_to_md(f.get('description') or '(no description)'))

links = f.get('issuelinks') or []
if links:
    print()
    print('## Linked Issues')
    print()
    for l in links:
        if 'inwardIssue' in l:
            i = l['inwardIssue']
            print(f'- **{l[\"type\"][\"inward\"]}** [{i[\"key\"]}](http://jira.cubrid.org/browse/{i[\"key\"]}): {i[\"fields\"][\"summary\"]} ({i[\"fields\"][\"status\"][\"name\"]})')
        if 'outwardIssue' in l:
            o = l['outwardIssue']
            print(f'- **{l[\"type\"][\"outward\"]}** [{o[\"key\"]}](http://jira.cubrid.org/browse/{o[\"key\"]}): {o[\"fields\"][\"summary\"]} ({o[\"fields\"][\"status\"][\"name\"]})')

comments = (f.get('comment') or {}).get('comments') or []
if comments:
    print()
    print('## Comments (' + str(len(comments)) + ')')
    print()
    for c in comments:
        print(f'### {c[\"author\"][\"displayName\"]} — {c[\"created\"][:10]}')
        print()
        print(jira_to_md(c['body']))
        print()
"
```

2. Present the output to the user as-is. The script formats everything into readable markdown with JIRA wiki markup converted via pandoc.
3. If the curl command fails or returns an error, inform the user that the JIRA instance may be unreachable.

$ARGUMENTS
