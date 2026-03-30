#!/usr/bin/env python3
"""Fetch a CUBRID JIRA issue and format it as markdown.

Usage: jira_fetch.py CBRD-XXXXX
       curl ... | jira_fetch.py  (reads JSON from stdin)
"""

import json
import subprocess
import sys
import urllib.request


JIRA_API = "http://jira.cubrid.org/rest/api/2/issue"
FIELDS = (
    "summary,status,priority,assignee,reporter,description,comment,"
    "issuelinks,fixVersions,versions,issuetype,parent,labels,created,"
    "updated,resolution,components"
)


def jira_to_md(text):
    if not text:
        return ""
    result = subprocess.run(
        ["pandoc", "-f", "jira", "-t", "gfm", "--wrap=none"],
        input=text,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else text


def format_issue(data):
    f = data["fields"]
    lines = []
    out = lines.append

    out(f'# {data["key"]}: {f.get("summary") or ""}')
    out("")
    out("| Field | Value |")
    out("|-------|-------|")
    out(f'| Type | {(f.get("issuetype") or {}).get("name", "N/A")} |')
    out(f'| Status | {(f.get("status") or {}).get("name", "N/A")} |')
    out(f'| Priority | {(f.get("priority") or {}).get("name", "N/A")} |')
    out(f'| Assignee | {(f.get("assignee") or {}).get("displayName", "Unassigned")} |')
    out(f'| Reporter | {(f.get("reporter") or {}).get("displayName", "N/A")} |')
    out(f'| Created | {(f.get("created") or "N/A")[:10]} |')
    out(f'| Updated | {(f.get("updated") or "N/A")[:10]} |')

    res = f.get("resolution")
    out(f'| Resolution | {res.get("name", "Unresolved") if res else "Unresolved"} |')

    if f.get("parent"):
        p = f["parent"]
        out(f'| Parent | {p["key"]}: {p["fields"]["summary"]} |')
    if f.get("fixVersions"):
        out(f'| Fix Version | {", ".join(v["name"] for v in f["fixVersions"])} |')
    if f.get("versions"):
        out(f'| Affects Version | {", ".join(v["name"] for v in f["versions"])} |')
    if f.get("labels"):
        out(f'| Labels | {", ".join(f["labels"])} |')
    if f.get("components"):
        out(f'| Components | {", ".join(c["name"] for c in f["components"])} |')

    out("")
    out("## Description")
    out("")
    out(jira_to_md(f.get("description") or "(no description)"))

    links = f.get("issuelinks") or []
    if links:
        out("")
        out("## Linked Issues")
        out("")
        for link in links:
            if "inwardIssue" in link:
                i = link["inwardIssue"]
                out(
                    f'- **{link["type"]["inward"]}** '
                    f'[{i["key"]}](http://jira.cubrid.org/browse/{i["key"]}): '
                    f'{i["fields"]["summary"]} ({i["fields"]["status"]["name"]})'
                )
            if "outwardIssue" in link:
                o = link["outwardIssue"]
                out(
                    f'- **{link["type"]["outward"]}** '
                    f'[{o["key"]}](http://jira.cubrid.org/browse/{o["key"]}): '
                    f'{o["fields"]["summary"]} ({o["fields"]["status"]["name"]})'
                )

    comments = (f.get("comment") or {}).get("comments") or []
    if comments:
        out("")
        out(f"## Comments ({len(comments)})")
        out("")
        for c in comments:
            out(f'### {c["author"]["displayName"]} \u2014 {c["created"][:10]}')
            out("")
            out(jira_to_md(c["body"]))
            out("")

    return "\n".join(lines)


def fetch_issue(ticket_id):
    url = f"{JIRA_API}/{ticket_id}?fields={FIELDS}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)


def main():
    if len(sys.argv) >= 2:
        ticket_id = sys.argv[1]
        try:
            data = fetch_issue(ticket_id)
        except Exception as e:
            print(f"Error fetching {ticket_id}: {e}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        data = json.load(sys.stdin)
    else:
        print("Usage: jira_fetch.py CBRD-XXXXX", file=sys.stderr)
        sys.exit(1)

    print(format_issue(data))


if __name__ == "__main__":
    main()
