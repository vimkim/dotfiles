# Chezmoi Dotfiles

Edit chezmoi sources in the checkout selected by `dot_codex/AGENTS.md`.
Preserve unrelated changes in the source checkout and deployed files.

## Workflow

1. Map each affected source to its absolute deployed file path; inspect both and edit only the source.
2. Review each target with `chezmoi --source <absolute-task-checkout> diff -- <absolute-target>` and run focused checks.
3. Follow the Git workflow in `dot_codex/AGENTS.md`: commit task changes, then request approval to rebase and fast-forward merge locally.
4. **After every approved merge, apply every affected dotfile from the merged source checkout:** run `chezmoi --source <absolute-merged-checkout> apply -- <absolute-target>` separately for each file. Merge approval authorizes this deployment; no separate deployment request is needed.
5. Verify each applied target with `chezmoi --source <absolute-merged-checkout> diff -- <absolute-target>`. Resolve or report remaining differences and any target that could not be applied.
6. Complete Git cleanup as specified in `dot_codex/AGENTS.md`; report the checkout, branch, commit, checks, applied targets, and any remaining dirt or blockers. Completion requires all affected targets applied and verified, plus Git cleanup.

Use one absolute file target per command. Never run a broad `chezmoi apply`
or use directory/glob targets. Repository synchronization requires an explicit
request; it does not authorize a broad apply. Push requires a separate request.

## Guidance sources

- Keep root `CLAUDE.md` identical to this file; both are repository-only guidance.
- Global guidance lives in `dot_codex/AGENTS.md`. Its targets are `$HOME/.codex/AGENTS.md` and `$HOME/.claude/CLAUDE.md`; verify and apply both separately. `dot_claude/CLAUDE.md.tmpl` includes the source, so edit only `dot_codex/AGENTS.md`.

## Context

- Before codebase exploration, read `docs/agents/domain.md`.
- For specs, tickets, or triage, use GitHub Issues in `vimkim/dotfiles`; first read `docs/agents/issue-tracker.md`.
- When assigning triage roles, read `docs/agents/triage-labels.md`.
