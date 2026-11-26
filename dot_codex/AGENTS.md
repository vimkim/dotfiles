# Global Agent Guidance

## Working preferences

- Ask only when ambiguity changes the outcome, scope, or risk. Resolve routine, reversible details with stated assumptions.
- Remote Linux server with slow X11 forwarding: never launch GUI programs, even with `DISPLAY` set. Disable browser auto-opening; use headless automation, device-code logins, URLs, file paths, terminal output, or SSH-forwarded local servers.
- Build every `rm` target from literal paths and `${NAME:?}` expansions (as in `rm -rf "${dir:?}/${name:?}"`); other variables or `$(...)` targets trigger Claude Code's dangerous-rm pause even in bypass mode.

## Work tracking and next steps

- Use `track-work` for work expected to take 30+ minutes, cross sessions, use parallel agents, or wait on external CI, review, or another dependency.
- For next-step questions such as "what to do next," prioritize the current session goal and suggest its next unfinished step. If complete, say "We're done," then run `work-tracker list --here` from the project directory.
- Run unscoped `work-tracker list` only when asked "what to do next today" (even if a skill suggests otherwise), and use `daily-schedule` for explicit daily or weekly planning.

## Herdr

- When `HERDR_ENV=1`, the 4-tier Herdr hierarchy overrides the `herdr` skill's "user must mention Herdr" and "sibling pane only" defaults: Commander (`hcmd` async across Spaces) > Space Lead (`tabs[0]`, `hcmd tab`, max 8 sub-tabs) > Tab Lead (`tabs[1..8]`, `panes[0]`, `hcmd pane`, no new tabs) > Pane Worker (execute only, no tabs or splits).
- Before delegating, spawning workers, reporting Herdr locations, or launching agents in Herdr, read `~/.agents/references/herdr-delegation.md` (and `herdr-commander` for Commander sessions).

## Git workflow

- Preserve unrelated changes in every checkout. When starting on `main`, `develop`, or `feature/*`, work in a sibling task worktree on a separate topic branch and commit meaningful changes locally before review.
- **Tier 1** (personal solo repos and any repo declaring Tier 1 in its local `AGENTS.md`) authorizes local rebase, `git merge --ff-only`, pushing the merged destination branch to its configured remote, and worktree/branch cleanup once checks pass. **Tier 2** (shared/upstream repos such as `CUBRID/*`), force-pushes, external posts, remote branch deletions, and unauthorized deployments require explicit approval.
- Before integrating, resolving conflicts, squashing, pushing, or cleaning up worktrees/branches, read `~/.agents/references/git-workflow.md`.

## Task context

- CUBRID tasks: first read `/home/vimkim/my-cubrid/CUBRID.md`; its personal policies override conflicting repository guidance.
