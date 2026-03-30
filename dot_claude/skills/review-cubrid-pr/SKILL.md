---
name: review-cubrid-pr
description: "CUBRID C/C++ PR code review with precondition validation, LSP/clangd analysis, and PR comment tracking. Use when reviewing a CUBRID pull request."
argument-hint: "<pr-url>"
model: opus
effort: max
allowed-tools: Bash(gh *), Bash(git *), Bash(jq *), Bash(curl *), Bash(${CLAUDE_SKILL_DIR}/scripts/*), Read, Glob, Grep, Agent, mcp__plugin_oh-my-claudecode_t__lsp_diagnostics, mcp__plugin_oh-my-claudecode_t__lsp_diagnostics_directory, mcp__plugin_oh-my-claudecode_t__lsp_hover, mcp__plugin_oh-my-claudecode_t__lsp_goto_definition, mcp__plugin_oh-my-claudecode_t__lsp_find_references, mcp__plugin_oh-my-claudecode_t__lsp_document_symbols
---

You are reviewing a CUBRID database engine pull request. Follow every step below precisely.

**PR URL (required):** $ARGUMENTS

---

## Step 1: Precondition Check

Run the prerequisite checker. If it fails, show the error verbatim and **stop immediately**.

```bash
${CLAUDE_SKILL_DIR}/scripts/check-prereqs.sh "$ARGUMENTS"
```

Parse the JSON output. Extract and save for later steps:
- `owner`, `repo`, `number` (for gh API calls)
- `head_sha` (for GitHub file links)
- `base_ref` (for diff range)
- `title`, `body`, `author`

---

## Step 2: Gather Context (parallel)

Launch these data-gathering steps **in parallel**:

### 2a. PR Diff
```bash
gh pr diff <NUMBER> -R <OWNER>/<REPO>
```
Save the full diff. Identify the list of changed files and their changed line ranges.

### 2b. Existing PR Comments
Fetch both review comments (inline) and issue comments (conversation):
```bash
# Inline review comments
gh api "repos/<OWNER>/<REPO>/pulls/<NUMBER>/comments" --jq '.[] | {id, user: .user.login, path, line: .original_line, in_reply_to_id, body, created_at}'

# Conversation comments
gh api "repos/<OWNER>/<REPO>/issues/<NUMBER>/comments" --jq '.[] | {id, user: .user.login, body, created_at}'
```
Save all comments. Group inline comments into threads (by `in_reply_to_id`). You must **not duplicate** points already raised.

### 2c. JIRA Context (if applicable)
If the PR title contains a `CBRD-XXXXX` ticket ID, fetch the JIRA issue:
```bash
curl -sL "http://jira.cubrid.org/rest/api/2/issue/CBRD-XXXXX?fields=summary,description,comment" 2>/dev/null
```
This gives the "why" behind the change. Evaluate whether the implementation matches intent.

### 2d. CLAUDE.md / AGENTS.md Files
Find all relevant CLAUDE.md and AGENTS.md files:
- Root `CLAUDE.md`
- Any in directories containing changed files (e.g., `src/transaction/AGENTS.md`)

Read them — they contain project-specific review criteria. Also read the reference file for CUBRID-specific review knowledge:
```
${CLAUDE_SKILL_DIR}/reference.md
```

---

## Step 3: Parallel Review (5 agents)

Launch **5 parallel Opus agents**. Each agent receives:
- The PR diff
- Changed files with line ranges
- Existing PR comments (to avoid duplication)
- Relevant CLAUDE.md/AGENTS.md content
- JIRA context (if available)

Each agent returns findings as JSON: `{file, line, severity, category, description, evidence}`.

### Agent 1: CUBRID Anti-Pattern Check
Check the diff against CUBRID-specific rules (see `reference.md` for the full checklist):
- `free()` without `free_and_init()` → **must flag**
- `#pragma once` instead of `#ifndef _FILENAME_H_` guards → **must flag**
- `memory_wrapper.hpp` not last include or missing `// XXX: SHOULD BE THE LAST INCLUDE HEADER` → **must flag**
- Bare `malloc`/`free` in server code instead of `db_private_alloc`/`free_and_init` → flag
- C++ exceptions in engine C code → flag
- `er_set()` without proper error propagation → flag
- Wrong naming convention → flag only if egregious
- Missing Apache 2.0 license on new files → flag
- `//` comments in `.c` files (must use `/* */`) → flag on new code only

### Agent 2: Logic & Correctness Bugs
For each changed function:
1. Read the **full function** (not just the diff hunk) for context
2. Check for: null dereference, off-by-one, use-after-free, uninitialized vars, missing error checks, resource leaks, wrong operator, logic inversions
3. Verify correctness of changed `if`/`switch`/`for` conditions
4. Focus on **real bugs** only. Ignore style and nitpicks.

### Agent 3: LSP/clangd Diagnostics
For each changed file:
1. Use `mcp__plugin_oh-my-claudecode_t__lsp_diagnostics` to get clangd diagnostics
2. Filter to diagnostics **on changed lines only**
3. Use `mcp__plugin_oh-my-claudecode_t__lsp_hover` on suspicious types/variables
4. If a function signature changed, use `mcp__plugin_oh-my-claudecode_t__lsp_find_references` to verify all callers updated

Report only errors/warnings on lines modified by this PR.

### Agent 4: Concurrency & Transaction Safety
Check the diff for:
- Lock ordering violations
- Missing lock before shared state access
- MVCC visibility issues (wrong snapshot)
- Page buffer: `pgbuf_fix` without `pgbuf_unfix`, dirty page not marked
- WAL protocol: data modification without proper log records
- Thread-safety of static/global variables
- Missing atomic operations on shared counters
- Deadlock potential

Only flag issues **introduced by this PR**, not pre-existing.

### Agent 5: PR Context & Historical Analysis
1. Summarize existing PR comments
2. Check if previous review feedback was addressed
3. `git log --oneline -20 -- <changed_files>` for recent history
4. Check for conflicts with recent commits to same functions
5. Flag issues raised in comments but **not yet addressed**

---

## Step 4: Score & Filter

Score each finding (0-100):

| Score | Action |
|-------|--------|
| 0-50 | **Drop** — false positive, pre-existing, or nitpick |
| 51-75 | **Include only** if LSP diagnostic or CLAUDE.md anti-pattern |
| 76-100 | **Include** — high confidence, real issue |

**Discard** findings that:
- Are pre-existing (not introduced by this PR)
- Were already raised in existing PR comments
- Would be caught by CI (compilation, formatting, linting)
- Are stylistic preferences not required by CLAUDE.md
- Are on unmodified lines

If no findings survive, go to Step 6.

---

## Step 5: Post Review

Post as **inline review comments** via the GitHub API:

```bash
gh api "repos/<OWNER>/<REPO>/pulls/<NUMBER>/reviews" \
  --method POST \
  -f event="COMMENT" \
  -f body="<SUMMARY>" \
  ...
```

Each inline comment body:
```
**[<CATEGORY>]** <description>

<evidence or code reference>
```

Categories: `anti-pattern`, `bug`, `concurrency`, `lsp-diagnostic`, `review-context`

Summary format:

```
### Code Review — PR #<NUMBER>

Reviewed <N> changed files, found <M> issues:

| # | File | Line | Category | Description |
|---|------|------|----------|-------------|
| 1 | `path/to/file.c` | L42 | bug | Brief description |

<sub>Reviewed with clangd LSP analysis. Checked CUBRID anti-patterns, concurrency safety, and correctness.</sub>
```

**Link formatting:** Use full SHA — `https://github.com/<OWNER>/<REPO>/blob/<HEAD_SHA>/<path>#L<start>-L<end>`

---

## Step 6: No Issues Path

Post a brief comment:
```
### Code Review — PR #<NUMBER>

No issues found. Reviewed <N> changed files for CUBRID anti-patterns, correctness bugs, concurrency safety, and clangd diagnostics.
```

---

## Rules

- **Never** post duplicate feedback — always check existing comments first
- **Never** flag pre-existing issues — only what this PR introduces
- **Never** suggest style/formatting changes that CI catches
- **Never** fabricate issues — false positives erode trust
- **Always** provide evidence (code snippet, LSP diagnostic, CLAUDE.md quote)
- **Always** use the full HEAD SHA in GitHub links
- Keep comments brief and actionable
- If a JIRA ticket exists, verify implementation matches intent
