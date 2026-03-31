---
name: cubrid-pr-create
description: Create a GitHub PR for the CUBRID project with [CBRD-XXXXX] title format and Korean body with English section headers. Use when the user wants to create a pull request for CUBRID changes.
---

# CUBRID PR Creator

Create GitHub pull requests for the CUBRID project following team conventions.

## When to Use

- User says "create pr", "make pr", "PR 만들어", "PR 올려", "풀리퀘"
- User wants to push changes and open a PR against CUBRID/CUBRID or a fork

## Arguments

Pass optional arguments to customize:

- `/cubrid-pr-create CBRD-26583` — Use this JIRA ticket number
- `/cubrid-pr-create CBRD-26583 feat/oos` — Ticket + base branch
- `/cubrid-pr-create` — Interactive: detect from branch name or ask

## Conventions

### Title Format

```
[CBRD-XXXXX] Short English description
```

- The JIRA ticket number is **required**. Extract from branch name (e.g., `cbrd-26583-oos-compact` → `CBRD-26583`) or ask the user.
- Description should be concise (<60 chars after the tag), in English.
- Use imperative mood: "Fix", "Add", "Refactor", "Support", not "Fixed", "Adding".

### Body Format

- **Section headers (`##`)**: Always in **English**
- **Body text**: Always in **Korean**
- **Code snippets, function names, file paths**: Keep as-is (English/code)

### Required Sections

The JIRA issue link **must** appear at the very top of the PR body, before any section headers.

```markdown
https://jira.cubrid.org/browse/CBRD-XXXXX

## Description
(변경 사항에 대한 배경 및 설명)

## Implementation
(구현 방법 및 주요 변경 사항 요약)

## Remarks
(참고 사항, 주의점, 후속 작업 등)
```

### Optional Sections

Add when relevant:

- `## Test Plan` — 테스트 방법 및 검증 계획
- `## Related Issues` — 관련 JIRA 이슈 또는 PR 링크

## Execution Steps

### Step 1: Gather Context

Run these in parallel:

1. `git status` — check for uncommitted changes
2. `git branch -vv` — current branch and tracking info
3. `git remote -v` — available remotes

If there are uncommitted changes, warn the user and ask whether to proceed or commit first.

### Step 2: Determine PR Parameters

1. **JIRA ticket**: Extract from arguments, branch name (`cbrd-XXXXX` or `CBRD-XXXXX` pattern), or ask.
2. **Base branch**: If not specified, detect:
   - For `feat/oos*` branches → base is `feat/oos`
   - For `CBRD-*` branches → base is `develop`
   - For `cubvec/*` branches → base is `cubvec/cubvec`
   - Otherwise ask the user
3. **Target repo**: Default `CUBRID/CUBRID`. Use `--repo` if different.
4. **Source**: Determine the user's fork remote (typically `vk` for `vimkim/cubrid`). The head ref format is `<github-user>:<branch>`.

### Step 3: Analyze Changes

1. Fetch the base branch: `git fetch <upstream-remote> <base-branch>`
2. Show commits: `git log --oneline <upstream>/<base>..HEAD`
3. Show diff stat: `git diff <upstream>/<base>...HEAD --stat`
4. Read the full diff to understand all changes.
5. If a JIRA ticket was identified, fetch context with `/jira CBRD-XXXXX` for richer description.

### Step 4: Draft PR Content

Based on the diff analysis:

1. **Title**: `[CBRD-XXXXX] Imperative English summary`
2. **Body**: Start with the JIRA link on the first line, then Korean text with English `##` headers:
   - `https://jira.cubrid.org/browse/CBRD-XXXXX` — 맨 위에 JIRA 이슈 링크
   - `## Description` — 왜 이 변경이 필요한지 배경 설명
   - `## Implementation` — 주요 변경 내용을 bullet points로 정리. 파일명, 함수명 포함.
   - `## Remarks` — 리뷰어가 알아야 할 참고 사항, 제한 사항, 후속 작업

Show the draft to the user and ask for confirmation before creating.

### Step 5: Push and Create PR

1. Push the branch to the user's fork:
   ```bash
   git push <fork-remote> <branch> -u
   ```
2. Create the PR using `gh`:
   ```bash
   gh pr create --repo CUBRID/CUBRID \
     --base <base-branch> \
     --head <user>:<branch> \
     --title "[CBRD-XXXXX] Title" \
     --body "$(cat <<'EOF'
   https://jira.cubrid.org/browse/CBRD-XXXXX

   ## Description
   한국어 설명...

   ## Implementation
   한국어 구현 내용...

   ## Remarks
   한국어 참고 사항...
   EOF
   )"
   ```
3. Print the resulting PR URL.

## Example Output

```
PR created: https://github.com/CUBRID/cubrid/pull/6950

Title: [CBRD-26583] Re-enable OOS OID replacement in heap records
Base:  feat/oos
Head:  vimkim:feat/oos-replace-oos-oid
```

## Tips

- If the branch has already been pushed, skip the push step.
- If a PR already exists for the branch, show it instead of creating a duplicate.
- For multi-commit PRs, summarize the overall change rather than listing each commit message.
- Always use `gh pr create` with heredoc for the body to handle multi-line Korean text correctly.
