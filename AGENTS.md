# Chezmoi Dotfiles Repository

This repository contains the chezmoi source of truth for managed dotfiles.
Make task edits in a sibling Git worktree, never in deployed counterparts
under `$HOME`.

## Safe dotfile workflow

For every dotfile change:

1. Identify the source file and its exact deployed target path before editing.
   Chezmoi naming rules mean, for example, `dot_zshrc` deploys as `~/.zshrc`.
2. Inspect the existing source and target as needed. Preserve user changes that
   are unrelated to the request; a dirty worktree is normal in this repository.
3. Change only the relevant chezmoi source file. Do not edit the deployed
   target directly, since a later targeted apply would replace that edit.
4. Verify the rendered change for that target, normally with
   `chezmoi --source <absolute-task-worktree> diff -- <target-path>` when
   working in a sibling worktree. Use an additional focused syntax or command
   check when the file type makes one appropriate.
5. If the user explicitly requests deployment, apply exactly that verified target:
   `chezmoi apply -- <target-path>`. Use the absolute target path or a quoted
   path rooted at `$HOME`; never rely on an ambiguous relative path.
6. Re-check that one target after applying when practical, then report both the
   source file and target path changed.

`<target-path>` always means one concrete managed destination, such as
`$HOME/.zshrc` or `$HOME/.config/nushell/config.nu`. Resolve it before running
the command; do not use a directory, glob, or a list of unrelated files.

## Deployment boundary

Never run a broad `chezmoi apply`, including after `chezmoi update` or
`chezmoi git pull`. This repository may coexist with important local changes
that are not yet managed or version controlled, and a broad apply can overwrite
them. The same restriction applies even when the requested source change is
small: always use `chezmoi apply -- <one-specific-target-path>`.

Do not run `chezmoi update` as part of a dotfile-editing task unless the user
explicitly requests repository synchronization. If synchronization is requested,
inspect the resulting diff and still deploy only named target paths.

## Git and handoff

Follow the worktree and review workflow in `dot_codex/AGENTS.md`: work on a
sibling topic worktree, verify the changes, and commit before asking for review.
Keep the task worktree clean at handoff, except during grilling or when an error
prevents completion; report any exception. Stage only task files and preserve
unrelated user changes. Put disposable outputs in narrowly scoped `.gitignore`
entries and commit those entries too.

User approval of the reviewed work authorizes merging into `main`. Push and
chezmoi deployment each require an explicit request. After an approved merge,
verify any requested deployment against the main source tree and apply each
concrete target separately. Report the committed review result and request
review of that result; do not bundle review approval with push or deployment.

Keep root `CLAUDE.md` identical to this file when changing repository guidance.

## Global agent instructions

Global instructions live only in `dot_codex/AGENTS.md` (deployed as
`~/.codex/AGENTS.md`). `dot_claude/CLAUDE.md.tmpl` includes that file through a
chezmoi template, so any edit to `dot_codex/AGENTS.md` automatically becomes
the content of `~/.claude/CLAUDE.md` as well. Edit only `dot_codex/AGENTS.md`;
do not copy the text into `dot_claude/CLAUDE.md.tmpl` or edit either deployed
file. When verifying or deploying such a change, handle both targets, each as
its own command: `$HOME/.codex/AGENTS.md` and `$HOME/.claude/CLAUDE.md`.

## Agent skills

### Issue tracker

For specs, tickets, and triage, use GitHub Issues in `vimkim/dotfiles`.
Read `docs/agents/issue-tracker.md` before tracker work.

### Triage labels

Use `docs/agents/triage-labels.md` when assigning triage roles.

### Domain docs

This is a single-context repository. Before codebase exploration, read
`docs/agents/domain.md` for glossary and ADR conventions.
