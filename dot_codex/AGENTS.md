# Global Agent Guidance

## Working preferences

- Ask only when ambiguity changes the outcome, scope, or risk. Resolve routine, reversible details with stated assumptions.
- Use `work-tracker` for work expected to take 30+ minutes, cross sessions, use parallel agents, or wait on an external queue.

## Next-step requests

- For next-step questions such as “what to do next,” default to the session goal and review progress first. Suggest the next unfinished step within that goal. If the goal is complete, say “We’re done,” then run `work-tracker list --here` from the session's project directory and report any remaining local work.
- Run `work-tracker list` without `--here` only when the user asks “what to do next today.” This includes filtered or JSON forms and applies even when a skill suggests an unscoped listing.

## Remote environment

Remote Linux server with slow X11 forwarding: never launch GUI programs, even with `DISPLAY` set. Disable browser auto-opening. Use headless automation, device-code logins, URLs, file paths, terminal output, or SSH-forwarded local servers.

## Git workflow

1. Inspect the branch, worktrees, and status. Preserve unrelated changes throughout.
2. Choose the checkout from the starting branch:
   - `main`, `develop`, or `feature/*`: create or reuse a sibling task worktree on a separate topic branch based on it. Record the starting branch as the merge destination.
   - Other named branches: use the current checkout. Use the repository's documented or agreed integration destination.
3. Run focused checks, review the diff, and commit all meaningful task changes before review; local task commits are authorized. Stage only task files. Ignore only disposable outputs with narrow `.gitignore` rules. Report checkout, branch, commit, checks, limitations, and unrelated dirt.
4. Ask once for approval to rebase onto the current local destination and merge locally, with squash as a fallback. Deployment requires an explicit request unless repository guidance includes it in merge approval.
5. After approval, verify the destination checkout is clean and on the expected branch. Rebase the task branch onto the destination's current tip, resolve conflicts, review the diff, run proportionate checks, then merge with `git merge --ff-only <rebased-task-commit>`. Repeat under the same approval if the destination advances. Ask again only if the result or a failure's impact is uncertain; report understood failures.
6. If rebase and fast-forward are impractical, abort any active rebase and run `git merge --squash <task-branch>` in the destination checkout. Resolve conflicts, review the staged diff, run proportionate checks, and commit under the same approval.
7. After each merge, complete required post-merge steps, including authorized deployment. Verify the destination includes the task tip or the squash commit preserves all task changes. If the merge destination is `main`, run `git push <remote> main` using its configured remote; merge approval authorizes this push. Pushes to other branches require a separate explicit request. Preserve valuable uncommitted or ignored files. From outside any merged linked task worktree, run `git worktree remove <task-worktree>`, then `git branch -d <task-branch>`. Clean up only this task's worktree and branch, without force; report obstacles. Finish with a clean destination. Remote branch deletion requires an explicit request.

Grilling sessions or errors may leave work uncommitted; report the remaining changes and next step.

## Task context

- Explicit daily or weekly planning: use `daily-schedule`, backed by `/home/vimkim/temp/todays-schedule` and `work-tracker`. Ordinary next-step questions follow the session rule above.
- CUBRID tasks: first read `/home/vimkim/my-cubrid/CUBRID.md`; its personal policies override conflicting repository guidance.
