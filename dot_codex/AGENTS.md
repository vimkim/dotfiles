# Global Agent Guidance

## Working preferences

- Clarify only ambiguities that change the outcome, scope, or risk; resolve routine, reversible details with stated assumptions.
- Use `work-tracker` for work expected to last at least 30 minutes, cross sessions, use parallel agents, or wait on an external queue.

## Remote environment

This is a remote Linux server with slow X11 forwarding. Never launch GUI programs, even when `DISPLAY` is set. Disable browser auto-opening; use headless automation and device-code logins. Share URLs, file paths, terminal output, or SSH-forwarded local servers.

## Git workflow

1. Inspect the current branch, worktrees, and status. Preserve unrelated user changes throughout.
2. Choose the checkout by the starting branch:
   - `main`, `develop`, or `feature/*`: create or reuse a sibling task worktree with a separate topic branch based on that branch. Record the starting branch as the merge destination.
   - Any other named branch: work directly in the current checkout; do not create another worktree. For later integration, use the repository's documented or agreed destination.
3. Run focused checks, inspect the diff, and commit all meaningful task changes before review; local task commits are authorized. Stage only task files; ignore only disposable outputs with narrow `.gitignore` rules. Report the checkout, branch, commit, checks, limitations, and any unrelated dirt.
4. Request one approval to rebase onto the current local destination branch and fast-forward merge locally. Push requires a separate explicit request. Deployment requires an explicit request unless repository guidance already authorizes it as part of merge approval.
5. After approval, verify the destination checkout is clean and on the expected branch. Rebase the task branch, resolve conflicts, inspect the diff, and run proportionate checks. Ask again only when uncertain about the result or a failure's impact; report understood failures. Merge with `git merge --ff-only <rebased-task-commit>`. If the destination advances, repeat under the same approval.
6. After every successful rebase and fast-forward merge, complete repository-required post-merge steps (including deployment), then clean up: verify the task tip is included in the destination and preserve valuable uncommitted or ignored files. From outside any merged linked task worktree, run `git worktree remove <task-worktree>`, then safely delete the task branch with `git branch -d <task-branch>`. Clean up only that task's worktree and branch, without force; report any obstacle. Finish with a clean destination checkout. Remote branch deletion requires an explicit request.

Grilling sessions or errors may leave work uncommitted; report the remaining changes and next step.

## Task context

- Daily or weekly planning: use `daily-schedule`, backed by `/home/vimkim/temp/todays-schedule` and the `work-tracker` ledger.
- CUBRID tasks: first read `/home/vimkim/my-cubrid/CUBRID.md`; its personal policies override conflicting repository guidance.
