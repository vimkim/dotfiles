# Tiered Git Workflow

Apply these rules to every repository you change. Preserve unrelated changes in every checkout throughout.

## Tiers and authorization

- **Tier 1** covers solo personal repositories such as `my-cubrid-docs`, `my-cubrid-jira`, `my-cubrid-schedule`, `my-cubrid-skills`, `my-skills`, `my-cubrid-workflow`, `chezmoi`, personal tools, and any repository declaring Tier 1 in its local `AGENTS.md`. Once checks pass, local rebase, `git merge --ff-only`, pushing the merged destination branch to its configured remote (for `main` or any destination branch with a configured remote or upstream), and cleanup of the merged task worktree and branch are authorized.
- **Tier 2** covers shared and upstream repositories such as `CUBRID/*`. Obtain explicit human approval before integration or push.
- **Always require explicit approval (both tiers)**: force-pushes, external posts, remote branch deletions, and deployments (unless repository guidance authorizes them).

## Step-by-step procedure

1. **Inspect**: Check branch, worktrees, and status; preserve unrelated changes throughout.
2. **Select checkout**:
   - Starting on `main`, `develop`, or `feature/*`: create or reuse a sibling task worktree on a separate topic branch based on it, and record the starting branch as the merge destination.
   - Starting on another named branch: use the current checkout and the repository's documented or agreed integration destination.
3. **Commit locally before review**: Run focused checks, review the diff, and commit all meaningful task changes locally (local task commits are authorized). Stage only task files; ignore only disposable outputs with narrow `.gitignore` rules. Report checkout, branch, commit, checks, limitations, and unrelated dirt. Grilling sessions or errors may leave work uncommitted — report remaining changes and next step.
4. **Approve integration (Tier 2)**: Ask once for approval to rebase onto the current local destination and merge locally (with squash as a fallback), including pushing the merged destination branch when applicable.
5. **Rebase and fast-forward merge**: Verify the destination checkout is clean and on the expected branch. Rebase the task branch onto the destination tip, resolve conflicts, review the diff, run proportionate checks, then merge with `git merge --ff-only <rebased-task-commit>`. Repeat under the same authorization if the destination advances; ask again only if the result or a failure's impact is uncertain, and report understood failures.
6. **Squash fallback**: If rebase and fast-forward are impractical, abort any active rebase and obtain explicit approval for a squash if not already granted. Run `git merge --squash <task-branch>` in the destination checkout, resolve conflicts, review the staged diff, run proportionate checks, and commit.
7. **Post-merge verification, push, and cleanup**:
   - Verify the destination includes the task tip (or the squash commit preserves all task changes).
   - If push is authorized and the merged destination branch has a configured upstream or remote (such as `main` with `origin`), run `git push <remote> <destination>` (pushing unmerged or other branches still requires an explicit request).
   - Preserve valuable uncommitted or ignored files before cleanup.
   - From outside any merged linked task worktree, run `git worktree remove <task-worktree>`, then `git branch -d <task-branch>` without force; report any obstacles and finish with a clean destination.
   - Remote branch deletion requires an explicit request.
