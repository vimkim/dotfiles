---
name: cubrid-pr-review
description: "CUBRID C/C++ PR code review with LSP/clangd analysis and C++ safety checks. Use when reviewing a CUBRID pull request, when the user shares a GitHub PR URL from a CUBRID repo, asks to review or check a pull request, or requests LSP-based analysis of PR changes. Even if the user just pastes a CUBRID PR link without explicit instructions, this skill applies."
argument-hint: "<pr-url>"
model: opus
effort: max
allowed-tools: Bash(gh *), Bash(git *), Bash(jq *), Bash(curl *), Bash(${CLAUDE_SKILL_DIR}/scripts/*), Read, Write, Glob, Grep, Agent, mcp__plugin_oh-my-claudecode_t__lsp_diagnostics, mcp__plugin_oh-my-claudecode_t__lsp_diagnostics_directory, mcp__plugin_oh-my-claudecode_t__lsp_hover, mcp__plugin_oh-my-claudecode_t__lsp_goto_definition, mcp__plugin_oh-my-claudecode_t__lsp_find_references, mcp__plugin_oh-my-claudecode_t__lsp_document_symbols
---

You are reviewing a CUBRID database engine pull request. CUBRID is a multi-threaded, open-source RDBMS with a large C/C++ codebase that has project-specific conventions (memory management macros, include ordering, error propagation patterns) that standard linters don't catch. This skill exists to catch those domain-specific issues and provide deep analysis that CI alone cannot.

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
which uv >/dev/null 2>&1 || { echo "Error: uv is not installed or not in PATH." >&2; exit 1; }
cubrid-jira-search CBRD-XXXXX
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

## Step 3: Parallel Review (3 agents)

Launch **3 parallel Opus agents**. Each agent receives:
- The PR diff
- Changed files with line ranges
- Existing PR comments (so agents don't re-raise points already discussed)
- Relevant CLAUDE.md/AGENTS.md content
- JIRA context (if available)

Each agent returns findings as JSON: `{file, line, severity, category, description, evidence}`.

### Agent 1: Logic & Correctness + LSP Analysis
For each changed function:
1. Read the **full function** (not just the diff hunk) for context
2. Check for: null dereference, off-by-one, use-after-free, uninitialized vars, missing error checks, resource leaks, wrong operator, logic inversions
3. Verify correctness of changed `if`/`switch`/`for` conditions
4. Focus on **real bugs** only. Ignore style and nitpicks.

For each changed file, also run LSP/clangd analysis:
1. Use `mcp__plugin_oh-my-claudecode_t__lsp_diagnostics` to get clangd diagnostics
2. Filter to diagnostics **on changed lines only**
3. Use `mcp__plugin_oh-my-claudecode_t__lsp_hover` on suspicious types/variables
4. If a function signature changed, use `mcp__plugin_oh-my-claudecode_t__lsp_find_references` to verify all callers updated

### Agent 2: C++ Safety & Memory Bug Risk
Check the diff for memory and concurrency safety issues:
- Use-after-free, double-free, missing `free_and_init()` after `free()`
- Bare `malloc`/`free` in server code instead of `db_private_alloc`/`free_and_init`
- Resource leaks: `pgbuf_fix` without `pgbuf_unfix`, `db_value` without `db_value_clear()`
- Lock ordering violations, missing lock before shared state access
- Thread-safety of static/global variables, missing atomic operations
- MVCC visibility issues, WAL protocol violations
- Deadlock potential
- Missing error propagation after `er_set()`

Only flag issues **introduced by this PR**, not pre-existing.

### Agent 3: PR Context & Historical Analysis
1. Summarize existing PR comments
2. Check if previous review feedback was addressed
3. `git log --oneline -20 -- <changed_files>` for recent history
4. Check for conflicts with recent commits to same functions
5. Flag issues raised in comments but **not yet addressed**

---

## Step 4: Filter

Discard findings that are:
- Pre-existing (not introduced by this PR)
- Already raised in existing PR comments
- Caught by CI (compilation, formatting, linting)
- Stylistic preferences not required by CLAUDE.md
- On unmodified lines

Every surviving finding needs **evidence**: a code snippet, LSP diagnostic, or rule citation.

If no findings survive, proceed to Step 5 (report will note no issues found).

---

## Step 5: Generate Report

After completing the review (whether issues were found or not), generate a Korean-language review report as a Markdown file. The report is in Korean because the CUBRID review team primarily communicates in Korean. The structured format below ensures reviewers can quickly scan scope, methodology, and findings without reading the full PR diff.

**File name:** `PR-<NUMBER>-report.md` in the repository root.

The report follows this structure (sections in Korean, headers with `##` for easy navigation):

```markdown
# PR #<NUMBER> 코드 리뷰 보고서

**PR:** [<OWNER>/<REPO>#<NUMBER>](https://github.com/<OWNER>/<REPO>/pull/<NUMBER>)
**제목:** <PR title>
**작성자:** <author>
**베이스 브랜치:** <base_ref>
**HEAD SHA:** `<head_sha>`
**리뷰 일시:** <today's date>

> **이 리뷰 보고서는 Claude Code (Opus 4.6, max effort)에 의해 자동 생성되었습니다.**
>
> 수행된 분석:
> - **3개 병렬 서브에이전트** 투입 (로직+LSP, C++ 안전성, PR 컨텍스트)
> - **LSP/clangd 정적 분석**: 변경된 파일에 대해 진단, 타입 호버, 참조 추적 수행
> - **JIRA 컨텍스트 교차 검증** (해당 시)
> - 기존 PR 코멘트 중복 제거 및 CI 중복 필터링 적용

---

## 1. PR 개요
<PR 목적 및 주요 변경 사항을 표로 정리>
<변경 파일 목록>

## 2. JIRA 컨텍스트
<JIRA 티켓 정보 요약 (해당 시)>

## 3. 리뷰 결과

### 3.1 로직/정확성 버그 + LSP 진단
<발견 사항 또는 "이슈 없음">

### 3.2 C++ 안전성 / 메모리 버그
<발견 사항 또는 "이슈 없음">

### 3.3 PR 컨텍스트/이력 분석
<기존 리뷰 코멘트 처리 현황 표>
<미응답 코멘트 표 (해당 시)>

## 4. 종합 평가
<결론 및 권장 사항>
```

Use the `Write` tool to create the file. Inform the user of the file path when done.

---

## Guiding Principles

- **Only flag issues introduced by this PR.** Not pre-existing problems.
- **Every finding needs evidence.** Code snippet, LSP diagnostic, or rule citation.
- **Check existing PR comments first.** Don't duplicate what's already raised.
- **Skip what CI catches.** No formatting, cppcheck, or compiler warning duplicates.
- **Use full HEAD SHA in GitHub links.**
- **Do not post comments to GitHub.** All findings go into the local report only.
- **If a JIRA ticket exists, verify implementation matches intent.**
