# Global Agent Guidance

## Working preferences

- Clarify only ambiguities whose answers could materially change the outcome, scope, or risk. Continue asking until those decisions are resolved; handle routine, reversible details with explicit assumptions.
- Track work with `work-tracker` when it is expected to take at least 30 minutes, cross sessions, use parallel agents, or wait on an external queue. Leave short, same-turn work unregistered.

## Worktree and review workflow

For repository changes, use a topic branch in a sibling Git worktree:

1. Inspect the branch, worktrees, and working-tree status. Create a task branch from `main` (or the repository's documented integration branch) with `git worktree add -b <task-branch> ../<repo>-<task> <base>`, or reuse the task's existing worktree. Make task edits there and preserve unrelated user changes.
2. Complete the work and relevant checks. Add narrowly scoped `.gitignore` entries for disposable task outputs; keep meaningful source, documentation, and verification artifacts tracked. Ignore rules must not conceal unfinished work or replace handling changes to already tracked files.
3. Before handing work back for review, inspect the diff, stage only task files, and commit all meaningful task changes, including `.gitignore` updates. Local task commits are authorized by this workflow. Verify `git status --short` is empty; report the worktree, branch, commit, checks, and any limitations.
4. A grilling session or an error that prevents completion may leave work uncommitted. In that case, report the reason, remaining changes, and next step. Preserve unrelated user changes rather than committing, discarding, or hiding them to obtain a clean status.
5. Keep the task branch available for review. Commit requested revisions and repeat the checks before handing it back. Merge into `main` (or the agreed integration branch) only after the user explicitly approves the reviewed work. Approval to merge does not authorize pushing or deploying.
6. Before merging, verify the destination worktree is clean and recheck the destination branch. Merge the approved commit with `git merge --ff-only <approved-commit>` when possible. If the destination has diverged, integrate it into the task branch, resolve conflicts, rerun relevant checks, and present the updated committed result for renewed approval before merging. Finish with a clean destination worktree and report the resulting commit.
7. After a successful merge, cleanup is part of completion: verify the task branch tip is included in the destination, inspect the task worktree for uncommitted and ignored files, and preserve anything valuable. From outside that worktree, run `git worktree remove <task-worktree>` and then `git branch -d <task-branch>`. Remove only the merged task’s worktree and local branch; avoid force removal or forced branch deletion. If cleanup is blocked, report the remaining path/branch and reason. Remote branch deletion requires explicit authorization for that remote action.

## Daily and weekly schedule

- When asked what to do today or next, what was planned, or to track a daily or weekly plan, use the `daily-schedule` skill. Its sources of truth are `/home/vimkim/temp/todays-schedule` and the `work-tracker` ledger.

## CUBRID

- For any CUBRID-related task, read and follow `/home/vimkim/my-cubrid/CUBRID.md` before acting. Its personal CUBRID policies override conflicting repository-local guidance.
