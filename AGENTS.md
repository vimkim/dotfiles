# Chezmoi Dotfiles

Follow `dot_codex/AGENTS.md` for checkout selection and the Git workflow.
Preserve unrelated source and deployed changes; edit sources only.

## Workflow

1. Map affected sources to absolute deployed targets and inspect both. Review each target with `chezmoi --source <absolute-task-checkout> diff -- <absolute-target>` and run focused checks.
2. Commit task changes, obtain local merge approval, and merge using the global Git workflow.
3. After every approved merge, run `chezmoi-apply-unmodified --source <absolute-merged-checkout>` once for all managed files and symlinks. Merge approval authorizes this deployment. See [helper usage and fallback](docs/chezmoi-apply-unmodified.md).
4. Verify affected targets with `chezmoi --source <absolute-merged-checkout> diff -- <absolute-target>`; an empty diff confirms deployment. Preserve and report helper skips and their remaining differences. Report command failures as blockers.
5. Complete Git cleanup. Report the checkout, branch, commit, checks, applied and skipped targets, and remaining dirt or blockers. Completion requires every affected target verified or explicitly skipped and reported, plus cleanup.

Use the helper for deployments. Repository synchronization and pushes require
explicit requests.

## Guidance sources

- Keep root `CLAUDE.md` identical to this file; both are repository-only guidance.
- Global guidance lives in `dot_codex/AGENTS.md`, deployed to `$HOME/.codex/AGENTS.md` and `$HOME/.claude/CLAUDE.md`. Edit only that source; `dot_claude/CLAUDE.md.tmpl` includes it.

## Context

- Before codebase exploration, read `docs/agents/domain.md`.
- For specs, tickets, or triage, use GitHub Issues in `vimkim/dotfiles`; first read `docs/agents/issue-tracker.md`.
- When assigning triage roles, read `docs/agents/triage-labels.md`.
