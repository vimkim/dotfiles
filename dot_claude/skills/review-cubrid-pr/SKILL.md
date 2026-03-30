---
name: review-cubrid-pr
description: "CUBRID C/C++ PR code review with precondition validation, LSP/clangd analysis, and PR comment tracking. Use when reviewing a CUBRID pull request, when the user shares a GitHub PR URL from a CUBRID repo, asks to review or check a pull request, wants code review for CUBRID changes, asks about anti-patterns in a PR, or requests LSP-based analysis of PR changes. Even if the user just pastes a CUBRID PR link without explicit instructions, this skill applies."
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

The review is split into 5 specialized agents because CUBRID bugs cluster into distinct domains — a concurrency expert catches lock ordering issues that a pattern checker would miss, and vice versa. Parallelism also keeps total review time reasonable despite the depth of each analysis.

Launch **5 parallel Opus agents**. Each agent receives:
- The PR diff
- Changed files with line ranges
- Existing PR comments (so agents don't re-raise points already discussed)
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

False positives erode reviewer trust — once an author sees a few bad flags, they start ignoring real ones too. This scoring step exists to keep precision high. The thresholds are calibrated so that only findings worth the author's attention survive.

Score each finding (0-100):

| Score | Action | Rationale |
|-------|--------|-----------|
| 0-50 | **Drop** | False positive, pre-existing, or nitpick — posting these wastes the author's time and trains them to ignore review comments |
| 51-75 | **Include only** if LSP diagnostic or CLAUDE.md anti-pattern | Mid-confidence findings are worth flagging only when backed by tool evidence or explicit project rules |
| 76-100 | **Include** | High confidence, real issue — these are the findings that justify the review |

Discard findings that fall into these categories (each represents a common false-positive source):
- Pre-existing issues (not introduced by this PR) — the author shouldn't fix unrelated tech debt in a focused PR
- Already raised in existing PR comments — duplicates add noise and suggest the reviewer didn't read the thread
- Would be caught by CI (compilation, formatting, linting) — redundant with automated checks
- Stylistic preferences not required by CLAUDE.md — subjective opinions don't belong in automated review
- On unmodified lines — same as pre-existing; out of scope

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

## Step 7: Generate Report

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
> - **5개 병렬 서브에이전트** 투입 (안티패턴, 로직/정확성, LSP/clangd, 동시성, PR 컨텍스트)
> - **LSP/clangd 정적 분석**: 변경된 파일에 대해 진단, 타입 호버, 참조 추적 수행
> - **CUBRID 도메인 전용 안티패턴** 검사 (`reference.md` 기반)
> - **JIRA 컨텍스트 교차 검증** (해당 시)
> - 기존 PR 코멘트 중복 제거 및 CI 중복 필터링 적용
> - 신뢰도 스코어링 (0-100)으로 오탐 최소화

---

## 1. PR 개요
<PR 목적 및 주요 변경 사항을 표로 정리>
<변경 파일 목록>

## 2. JIRA 컨텍스트
<JIRA 티켓 정보 요약 (해당 시)>

## 3. 리뷰 방법론
<사용된 에이전트 및 분석 영역을 표로 정리>

## 4. 리뷰 결과
### 4.1 CUBRID 안티패턴 검사
<검사 항목별 결과 표>

### 4.2 로직/정확성 버그
<발견 사항 또는 "이슈 없음">

### 4.3 LSP/clangd 진단
<진단 결과>

### 4.4 동시성/트랜잭션 안전성
<검사 항목별 결과 표>

### 4.5 PR 컨텍스트/이력 분석
<기존 리뷰 코멘트 처리 현황 표>
<미응답 코멘트 표 (해당 시)>

## 5. 종합 평가
<결론 및 권장 사항>
```

Use the `Write` tool to create the file. Inform the user of the file path when done.

---

## Guiding Principles

These principles exist because CUBRID engineers receive automated review comments alongside human reviews. If the automated review is noisy, inaccurate, or redundant, engineers learn to ignore it — which defeats the purpose.

- **Check existing comments before posting.** Duplicate feedback clutters the PR thread and signals that the reviewer didn't read the discussion. Group inline comments by `in_reply_to_id` in Step 2b specifically so you can detect threads.
- **Only flag issues introduced by this PR.** Authors shouldn't be asked to fix unrelated pre-existing problems in a focused change. If you notice a systemic pre-existing issue worth addressing, mention it in the report (Step 7) as a separate observation, not as a PR comment.
- **Skip what CI already catches.** CUBRID CI runs cppcheck, astyle, and compilation checks. Flagging formatting or compiler warnings duplicates that pipeline and adds noise.
- **Every finding needs evidence.** A code snippet, LSP diagnostic output, or CLAUDE.md rule citation. Unsupported claims ("this looks wrong") are not actionable and get ignored.
- **Use the full HEAD SHA in GitHub links** so links remain stable even after force-pushes. Short SHAs or branch-relative links break.
- **Generate the Korean report as the final step** — it serves as the permanent record of the review for the team, even when no issues are found.
- **Keep comments brief and actionable.** Engineers scan review comments quickly; a concise finding with evidence is more impactful than a lengthy explanation.
- **If a JIRA ticket exists, verify implementation matches intent.** The ticket captures the "why" — if the implementation diverges from the stated goal, that's worth flagging.
