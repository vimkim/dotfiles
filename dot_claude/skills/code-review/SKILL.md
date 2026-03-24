---
name: code-review
description: CUBRID database engine C/C++ PR code review skill. Performs comprehensive review covering CUBRID-specific patterns (error handling, page buffer management, locking, transactions), C/C++ correctness, concurrency safety, and database engine semantics. Use when reviewing PRs, diffs, or code changes in the CUBRID repository.
---

# CUBRID C/C++ Code Review

Perform a comprehensive code review of CUBRID engine C/C++ changes.

## Workflow

### Step 1: Gather Context

1. **Determine the base branch** — never assume `main`. Run `gh pr view <number> --json baseRefName` to find the target branch. Then diff with `git diff <remote>/<base_branch>...HEAD` (three dots). **IMPORTANT:** Always use `...` (three dots), not `..` (two dots). Two dots includes changes from the base branch itself, which leads to reviewing unrelated code and false findings. Three dots shows only changes introduced on the PR branch since the merge base. Run this separately from other parallel calls.
2. Fetch the diff with `gh pr diff <number>` if a PR number is given.
3. Identify touched CUBRID subsystems (storage, transaction, query, parser, optimizer, broker, etc.).
4. Read surrounding code for modified functions to understand full context.
5. Check the linked JIRA ticket (CBRD-XXXXX) via `/jira` for requirements context.

### Step 2: LSP Deep Analysis

Run thorough LSP analysis on every modified file. LSP tools are free and provide compiler-grade insights. Do NOT skip this step.

1. **Diagnostics scan** — Run `lsp_diagnostics` on EVERY modified file. Catches compiler warnings, type errors, implicit conversions, undefined behavior. Every warning/error is a high-confidence finding.
2. **Directory scan** — Use `lsp_diagnostics_directory` when many files in the same directory are modified.
3. **Symbol understanding** — For each non-trivial modified/added function:
   - `lsp_hover` on key symbols to verify type correctness and contracts
   - `lsp_goto_definition` on called functions to verify return values, side effects, ownership semantics
   - `lsp_document_symbols` to understand file structure
4. **Impact analysis** — For any function whose signature or semantics changed:
   - `lsp_find_references` to find ALL callers across the codebase
   - Flag callers that might break but aren't in the PR
5. **Cross-reference verification** — For new function calls or changed call patterns:
   - `lsp_goto_definition` to verify the function exists and arguments match
   - `lsp_hover` to confirm type compatibility at call sites
   - `lsp_code_actions` to check for clangd-suggested quick-fixes (often reveal real issues)

**Principle**: LSP gives the compiler's view. Use aggressively — every diagnostics warning is a potential CRITICAL/MAJOR finding. Every `lsp_find_references` result on a changed signature is a potential missed update.

### Step 3: Review Against Checklist

Read `references/cubrid-review-checklist.md` for the full review checklist covering:

1. Error handling patterns (return value checking, ASSERT_ERROR, cleanup)
2. Page buffer management (fix/unfix pairing, latch modes/ordering, dirty marking)
3. Lock and concurrency safety (critical sections, mutexes, TOCTOU races)
4. Transaction and logging safety (WAL, sysop boundaries, undo/redo)
5. Memory management (alloc/free pairing, buffer overflows, use-after-free)
6. C/C++ correctness (overflow, null deref, uninitialized vars, type casting)
7. Coding style (GNU-style braces, naming, include ordering)
8. Build mode awareness (SERVER_MODE / SA_MODE / CS_MODE)
9. Performance (hot paths, lock scope, I/O in critical sections)
10. Test adequacy (unit tests, error paths, concurrency tests)

Incorporate LSP findings from Step 2 into the severity ratings.

## Output Format

```markdown
## PR Review: [PR title]

### Summary
[1-2 sentence summary and overall assessment]

### Findings

#### [CRITICAL] Title
**File:** `path/to/file.c:LINE`
**Issue:** Description of the problem
**Suggestion:** How to fix it

#### [MAJOR] Title
...

### Positive Observations
[Well-done aspects worth reinforcing]

### Questions for Author
[Clarifying questions about design decisions]
```

## Tips

- Read the JIRA ticket before reviewing for full requirements context.
- Check git history of modified functions for recent related changes.
- When in doubt about CUBRID conventions, look at surrounding code in the same file.
- Pay extra attention to subsystem boundaries (e.g., storage calling transaction APIs).
- For large PRs, prioritize core logic changes over mechanical/boilerplate.
