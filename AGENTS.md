# Chezmoi Dotfiles

Follow `dot_codex/AGENTS.md` for checkout selection and the Git workflow (`chezmoi` is a Tier 1 repository).
Preserve unrelated source and deployed changes; edit sources only.

## Workflow

1. Map affected sources to absolute deployed targets and inspect both. Review each target with `chezmoi --source <absolute-task-checkout> diff -- <absolute-target>` and run focused checks.
2. Commit task changes, then integrate using the Tier 1 Git workflow in `dot_codex/AGENTS.md` (rebase onto the destination branch, `git merge --ff-only`, and push the merged destination branch when a remote is configured).
3. After merging into the configured source checkout, run `chezmoi-apply-unmodified` once for all managed files and symlinks. Tier 1 integration authorizes this deployment. See [helper usage and fallback](docs/chezmoi-apply-unmodified.md).
4. Verify affected targets with `chezmoi diff -- <absolute-target>`; an empty diff confirms deployment. Preserve and report helper skips and their remaining differences. Report command failures as blockers.
5. Complete Git cleanup (remove the merged task worktree and delete the local topic branch). Report the checkout, branch, commit, push, checks, applied and skipped targets, and remaining dirt or blockers. Completion requires every affected target verified or explicitly skipped and reported, plus push (when a remote is configured) and cleanup.

Use `chezmoi-apply-unmodified` for deployments. Pulling or syncing unrelated remote changes (`chezmoi update`, `git pull`, etc.) still requires an explicit request.

## Guidance sources

- Keep root `CLAUDE.md` identical to this file; both are repository-only guidance.
- Global guidance lives in `dot_codex/AGENTS.md`, deployed to `$HOME/.codex/AGENTS.md`, `$HOME/.claude/CLAUDE.md`, and `$HOME/.gemini/AGENTS.md`. Edit only that source; `dot_claude/CLAUDE.md.tmpl` and `dot_gemini/AGENTS.md.tmpl` include it.

## Context

- Before codebase exploration, read `docs/agents/domain.md`.
- For specs, tickets, or triage, use GitHub Issues in `vimkim/dotfiles`; first read `docs/agents/issue-tracker.md`.
- When assigning triage roles, read `docs/agents/triage-labels.md`.
