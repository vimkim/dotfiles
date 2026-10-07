# Issue Tracker: GitHub

Specs and tickets live in GitHub Issues in `vimkim/dotfiles`.
Use the `gh` CLI with `--repo vimkim/dotfiles` for tracker operations.
Keep long-running work status and history in `work-tracker` under the existing
global guidance; link relevant GitHub issues in its notes.

## Operations

Append `--repo vimkim/dotfiles` to the commands below.

- Publish a spec or ticket: `gh issue create --title TITLE --body-file FILE`.
- Fetch a ticket and discussion: `gh issue view NUMBER --comments`.
- Read structured context: `gh issue view NUMBER --json number,title,body,comments,labels,state,assignees,blockedBy,subIssues`.
- List open tickets: `gh issue list --state open --json number,title,body,labels,assignees`; filter by label when needed.
- Comment: `gh issue comment NUMBER --body-file FILE`.
- Apply or remove labels: `gh issue edit NUMBER --add-label LABEL` or `--remove-label LABEL`.
- Complete a ticket: `gh issue close NUMBER --reason completed`; use `--reason "not planned"` for declined work.

Use a temporary body file for multiline Markdown so actual newlines are
preserved. Use the label mapping in `triage-labels.md`; inspect existing labels
before adding missing mapped labels.

## Parents and blockers

Create blocker tickets first. Attach children with
`gh issue create --parent PARENT` or `gh issue edit CHILD --parent PARENT`.
Add native blockers with `gh issue create --blocked-by BLOCKERS` or
`gh issue edit CHILD --add-blocked-by BLOCKER`; these arguments are issue
numbers or URLs.

If native relationships are unavailable, use `Part of #PARENT` and
`Blocked by: #BLOCKER, #BLOCKER` in the child body.
A ticket is ready only when every blocker is closed.

## Wayfinding

The map is one issue labelled `wayfinder:map`; children use
`wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or
`wayfinder:task`, with parent and blocker relationships as above.

Choose an open, unassigned child whose blockers are closed, in map order.
Claim it with `gh issue edit NUMBER --add-assignee @me`.
Resolve it by posting its answer, closing it, and adding a short answer and
issue link to the map's Decisions-so-far.

## Pull requests

**PRs as a request surface: no.**

GitHub issues and PRs share a number space. Resolve ambiguous references with
`gh pr view NUMBER`, falling back to `gh issue view NUMBER`.
