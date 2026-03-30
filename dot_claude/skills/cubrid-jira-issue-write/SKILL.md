---
name: cubrid-jira-issue-write
description: Write a CUBRID JIRA issue report in Korean with English section headers (##). Analyzes codebase context, writes structured issue markdown to /home/vimkim/gh/my-cubrid-jira/issues/. Use when the user wants to write up a JIRA issue, document a bug finding, or create a feature/task report for CUBRID.
---

# CUBRID JIRA Issue Writer

Write structured JIRA issue reports for the CUBRID project. Output is a markdown file saved to `/home/vimkim/gh/my-cubrid-jira/issues/`.

## When to Use

- User says "write a jira issue", "jira로 작성", "이슈 작성", "리포트 작성"
- User has analysis results or findings to document as a JIRA issue
- User wants to formalize a bug report, feature request, or task

## Output Format

The issue file MUST follow these conventions:

### Language Rules

- **Section headers (`##`)**: Always in English
- **Subsection headers (`###`) and body text**: Always in Korean
- **Code snippets, function names, file paths**: Keep as-is (English/code)
- **Tables**: Korean content, English column headers are OK

### File Naming

`CBRD-XXXXX-short-slug.md` where XXXXX is the JIRA ticket number and short-slug is a brief English descriptor.

If no JIRA ticket number is provided, ask the user for it or use a descriptive name.

### Required Sections

Every issue MUST have these sections in this order:

```markdown
# [TAG] 한국어 제목

## Description

### 배경
(문제의 배경 설명)

### 목적
(이 이슈의 목적)

---

## Implementation
(or ## Spec Change, ## Analysis — pick the most appropriate)

(구현 방법, 변경 사항, 또는 분석 결과)

---

## Acceptance Criteria
(or ## A/C)

- [ ] 체크리스트 형태의 수락 조건

---

## Remarks

(참고 사항, 후속 작업, PR 링크 등)
```

### Optional Sections

Add these when relevant:

- `## Spec Change` — API/format changes with tables showing before/after
- `## Analysis` — For investigation/research issues
- `## 참고 코드` — Key source file references

### Style Guide

1. **Title format**: `# [TAG] 한국어 설명` — TAG is a short category like `[OOS]`, `[BTREE]`, `[BROKER]`
2. **Use `---` horizontal rules** between major sections
3. **Tables** for structured data (function lists, format changes, comparison)
4. **Code blocks** with language annotation for source code
5. **Flow diagrams** using ASCII art in code blocks for call chains
6. **Bold** for emphasis on key terms
7. **Backticks** for all function names, variable names, file paths, and code references
8. Keep paragraphs concise — prefer bullet points and tables over long prose
9. Acceptance criteria as markdown checkboxes (`- [ ]`)

## Reference Examples

Refer to existing issues in `/home/vimkim/gh/my-cubrid-jira/issues/` for style consistency. Key examples:

- `CBRD-26637-refactor-error-handling.md` — Refactoring issue with implementation details
- `CBRD-26630-oos-inline-length.md` — Spec change with before/after tables
- `CBRD-26609-oos-physical-delete.md` — New feature with call flow diagrams and WAL design

## Execution Steps

1. **Check output directory**: Verify that `/home/vimkim/gh/my-cubrid-jira/issues/` exists. If it does NOT exist, **stop immediately** and tell the user: "Error: Issue directory `/home/vimkim/gh/my-cubrid-jira/issues/` does not exist. Please clone or create the repository first." Do NOT create the directory automatically.
2. **Gather context**: Read relevant source code, prior analysis, or conversation context
3. **Determine sections**: Based on issue type (bug/feature/task/analysis), pick the right section mix
4. **Write the issue**: Follow the format above, in Korean with English `##` headers
5. **Save the file**: Write to `/home/vimkim/gh/my-cubrid-jira/issues/CBRD-XXXXX-slug.md`
6. **Show the user**: Print the file path and a brief summary

## Arguments

Pass the JIRA ticket number and/or topic as arguments:

- `/write-jira-issue CBRD-26583 OOS compact analysis` — Write issue for specific ticket
- `/write-jira-issue` — Interactive mode, ask user for details
