# Global Agent Guidance

## Working preferences

- Ask only when ambiguity changes the outcome, scope, or risk. Resolve routine, reversible details with stated assumptions.
- Use `work-tracker` for work expected to take 30+ minutes, cross sessions, use parallel agents, or wait on external CI, review, or another dependency. Skip single-session work under 30 minutes unless it waits on external CI or review.
- Use `waiting` for external CI, review, or a user response. Reserve `blocked` for technical, permission, or dependency impediments that prevent progress.
- Keep at most five items `active`. Demote items untouched for more than three days to `pending`, or to `waiting` or `blocked` when their current state warrants it.

## Herdr

- When reporting a Herdr location, include the workspace name, tab name, and full target ID, for example `CBRD-28035, tab sa-rollback-issue (w2GX:t2), pane w2GX:p2`. Read the names and IDs from the live API.

- When asked to use `ai-round`, run `herdr pane run <pane-id> ai-round` in the target workspace. The launcher supplies Claude's settings path and bypass flag.
- For direct `codex` and `claude` launches through Herdr, default to bypass mode unless the user requests another mode. Pass native options after `--` with `herdr agent start`, or directly to the executable with `herdr pane run`.
  - Codex uses `--profile local --dangerously-bypass-approvals-and-sandbox`.
  - Claude uses `--settings <absolute-path> --dangerously-skip-permissions`. Resolve the absolute path to `local-settings.json` in `CLAUDE_CONFIG_DIR` when set and nonempty, or in `~/.claude` otherwise. Pass the resolved path as one argument.
- Verify the running agent's permission mode before submitting work, including after shell alias launches and session restores.

## Next-step requests

- For next-step questions such as “what to do next,” default to the session goal and review progress first. Suggest the next unfinished step within that goal. If the goal is complete, say “We’re done,” then run `work-tracker list --here` from the session's project directory and report any remaining local work.
- Run `work-tracker list` without `--here` only when the user asks “what to do next today.” This includes filtered or JSON forms and applies even when a skill suggests an unscoped listing.

## Remote environment

Remote Linux server with slow X11 forwarding: never launch GUI programs, even with `DISPLAY` set. Disable browser auto-opening. Use headless automation, device-code logins, URLs, file paths, terminal output, or SSH-forwarded local servers.

## Shell commands

- Build every `rm` target from literal paths and `${NAME:?}` expansions, as in `rm -rf "${dir:?}/${name:?}"`. Claude Code's dangerous-rm check stops for human approval on any other variable or `$(...)` target, even in bypass mode, and the agent waits until someone answers.

## Git workflow

### Tiered Git integration

- **Tier 1** covers solo personal repositories such as `my-cubrid-docs`, `my-cubrid-schedule`, `my-cubrid-skills`, `my-skills`, `my-cubrid-workflow`, `chezmoi`, and personal tools. Once checks pass, local rebase, `git merge --ff-only`, push to `main`, and cleanup of the merged task worktree and branch are authorized.
- **Tier 2** covers shared and upstream repositories such as `CUBRID/*`. Obtain explicit human approval before integration or push in these repositories. Deployments, force-pushes, and external posts also require explicit human approval in either tier.

1. Inspect the branch, worktrees, and status. Preserve unrelated changes throughout.
2. Choose the checkout from the starting branch:
   - `main`, `develop`, or `feature/*`: create or reuse a sibling task worktree on a separate topic branch based on it. Record the starting branch as the merge destination.
   - Other named branches: use the current checkout. Use the repository's documented or agreed integration destination.
3. Run focused checks, review the diff, and commit all meaningful task changes before review; local task commits are authorized. Stage only task files. Ignore only disposable outputs with narrow `.gitignore` rules. Report checkout, branch, commit, checks, limitations, and unrelated dirt.
4. For Tier 2, ask once for approval to rebase onto the current local destination and merge locally, with squash as a fallback. Include the push to `main` in the approval when applicable.
5. Verify the destination checkout is clean and on the expected branch. Rebase the task branch onto the destination's current tip, resolve conflicts, review the diff, run proportionate checks, then merge with `git merge --ff-only <rebased-task-commit>`. Repeat under the same authorization if the destination advances. Ask again only if the result or a failure's impact is uncertain. Report understood failures.
6. If rebase and fast-forward are impractical, abort any active rebase. Obtain explicit approval for a squash if it has not already been granted. Run `git merge --squash <task-branch>` in the destination checkout, resolve conflicts, review the staged diff, run proportionate checks, and commit.
7. After each merge, complete authorized post-merge steps. Verify the destination includes the task tip or the squash commit preserves all task changes. If authorized to push to `main`, run `git push <remote> main` using its configured remote. Pushes to other branches require an explicit request. Preserve valuable uncommitted or ignored files. From outside any merged linked task worktree, run `git worktree remove <task-worktree>`, then `git branch -d <task-branch>`. Clean up only this task's worktree and branch without force and report obstacles. Finish with a clean destination. Remote branch deletion requires an explicit request.

Grilling sessions or errors may leave work uncommitted; report the remaining changes and next step.

## Task context

- For explicit daily or weekly planning, use `daily-schedule`, backed by `/home/vimkim/temp/my-cubrid-schedule` and `work-tracker`. Ordinary next-step questions follow the session rule above.
- CUBRID tasks: first read `/home/vimkim/my-cubrid/CUBRID.md`; its personal policies override conflicting repository guidance.
