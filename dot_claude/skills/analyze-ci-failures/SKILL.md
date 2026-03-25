---
name: analyze-ci-failures
description: Analyze CircleCI/CI shell test failures for CUBRID PRs. Reads failed TC list, fetches CI results, reads test scripts and answer files, categorizes failures by root cause, and generates a structured report. Use when CI tests fail and the user wants to understand why.
---

# CUBRID CI Test Failure Analyzer

Analyze failed shell test cases from CircleCI (or other CI) for CUBRID PRs. Produces a categorized report with root cause analysis and fix proposals.

## When to Use

- User says "analyze ci failures", "CI 실패 분석", "왜 TC 실패했어", "failed tc 분석"
- User shares a CircleCI URL with test failures
- User has a `failed_tc.txt` or similar list of failed test cases
- User wants to understand why shell tests failed on a PR

## Arguments

- `/analyze-ci-failures` — Interactive: look for `failed_tc.txt` in cwd
- `/analyze-ci-failures <circleci-url>` — Fetch failures from CircleCI
- `/analyze-ci-failures <file>` — Read failure list from specified file

## Inputs

The skill needs:

1. **Failed TC list**: A file listing failed test case paths (e.g., `failed_tc.txt`), or a CircleCI URL to fetch from
2. **Test case directory**: A directory containing the actual test scripts and answer files (e.g., `~/cubrid-testcases-private-ex`)
3. **Feature context**: The branch/PR being tested (to understand what changes might cause failures)

## Execution Steps

### Step 1: Gather Inputs

1. Locate the failed TC list:
   - Check arguments for a file path or CircleCI URL
   - Check cwd for `failed_tc.txt`
   - Ask user if not found
2. Identify the test case base directory:
   - Check if `~/cubrid-testcases-private-ex` exists
   - Check additional working directories
   - Ask user if not found
3. Identify the feature branch context:
   - `git branch --show-current`
   - `git log --oneline HEAD --not develop | head -20` to understand feature changes

### Step 2: Fetch CI Failure Details

If a CircleCI URL is provided, use an agent to fetch the actual test failure messages (diffs, error outputs). This provides the actual vs expected output, which is critical for root cause analysis.

### Step 3: Read All Failed Test Cases (Parallel)

For each failed TC:

1. **Read the test script** (`.sh` file in `cases/` directory)
2. **Read the answer file** (`.answer` file — expected output)
3. **Read supporting SQL files** (`.sql` files used by the test)
4. **Note what the test does**: data types involved, operations tested (CRUD, unload/load, copydb, diagdb, etc.)

Use parallel reads — launch all file reads at once since they're independent.

### Step 4: Analyze Feature Changes

Understand what the feature branch changes that could cause failures:

1. Read key modified source files (use `git diff develop...HEAD --stat`)
2. Identify behavioral changes:
   - New file types or storage mechanisms
   - Changed output formats (diagdb, show heap header, etc.)
   - Disabled or stubbed functions
   - New error codes or changed error messages
3. Use explore agents in parallel for deeper code analysis if needed

### Step 5: Categorize and Analyze

For each failed TC, determine:

1. **Is it related to the feature?** — Match test operations against feature changes
2. **Root cause hypothesis** — Why the test fails given the feature changes
3. **Category** — Group TCs by shared root cause

Common categories:
- Output format mismatch (answer file needs update)
- Disabled/stubbed functionality
- New storage path not handled by existing tool (unloaddb, copydb, etc.)
- Error code changes
- Timeout / CI flakiness
- Unrelated regression

### Step 6: Generate Report

Write a structured markdown report with:

```markdown
# Failed TC Analysis Report: <branch> (<PR link>)

## Background
(Feature description, key behavioral changes)

## Category N: <Root Cause> (X TCs) — <OOS-related? / Feature-related?>

| # | TC | What it tests | Failure | Related? |
|---|-----|--------------|---------|----------|
| ... | ... | ... | ... | ... |

**Root cause analysis**: ...
**Proposed fix**: ...

## Summary

| Category | Count | Related? | Root Cause |
|----------|-------|----------|------------|
| ... | ... | ... | ... |

## Priority Actions
1. P0: ...
2. P1: ...
```

### Step 7: Save and Present

1. Save report to `failed_tc_report.md` in the project root (or user-specified location)
2. Print a concise summary with counts: X related, Y unrelated, Z total

## Output Conventions

### Language

- **Section headers (`##`)**: English
- **Table content and analysis**: English (technical report for broad audience)
- **Code, paths, function names**: Keep as-is

### Style

- Tables for TC listings within each category
- Code blocks for call flow diagrams showing broken vs expected paths
- Bold for key findings and root causes
- Backticks for all code references
- Horizontal rules between major sections

## Tips

- **When in doubt about source code behavior, use LSP (clangd)** to analyze CUBRID C/C++ code. Use `lsp_hover` to check types, `lsp_goto_definition` to trace function implementations, `lsp_find_references` to understand call sites, and `lsp_diagnostics` to catch issues. This is especially useful when tracing how a changed function affects downstream callers.
- **When fetching CircleCI results, use API v1.1** (not v2) since v2 requires authentication. Example: `https://circleci.com/api/v1.1/project/github/CUBRID/cubrid/<build_num>/tests` works without credentials.
- Always read the actual test script AND answer file — the script tells you what operations are tested, the answer tells you what output is expected
- Look for data types that exceed storage thresholds (e.g., `varchar(20000)`, large JSON, CLOB/BLOB)
- Check for `diagdb`, `show heap header`, `cubrid spacedb` in test scripts — these are sensitive to storage format changes
- Check for `unloaddb`/`loaddb`/`copydb` — these require full record resolution
- TCs with no diff details from CI may need local reproduction to diagnose
- Group by root cause, not by symptom — multiple TCs often share a single underlying issue
