# Chezmoi Dotfiles Repository

This directory is the chezmoi source repository. Treat it as the source of
truth for managed dotfiles: edit source files here, never their deployed
counterparts under `$HOME`.

## Safe dotfile workflow

For every dotfile change:

1. Identify the source file and its exact deployed target path before editing.
   Chezmoi naming rules mean, for example, `dot_zshrc` deploys as `~/.zshrc`.
2. Inspect the existing source and target as needed. Preserve user changes that
   are unrelated to the request; a dirty worktree is normal in this repository.
3. Change only the relevant chezmoi source file. Do not edit the deployed
   target directly, since a later targeted apply would replace that edit.
4. Verify the rendered change for that target, normally with
   `chezmoi diff -- <target-path>`. Use an additional focused syntax or command
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

Do not commit, push, or apply a change unless the user explicitly asks for that
operation. Before a commit, inspect `git status --short` and stage only the
files belonging to the request; never absorb pre-existing changes.

When the source change and focused verification are ready, tell the user
exactly: `say 'yes' and I will proceed 'chezmoi apply -- <specific-target-path>, git commit, git push'`.
