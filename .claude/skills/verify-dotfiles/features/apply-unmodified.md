# Apply only unmodified targets

`chezmoi-apply-unmodified` is how merged changes reach the home. It applies every target that is unchanged since chezmoi last wrote it, and it skips a locally edited or deleted target with `Skipped locally changed target: <path>`, keeping the user's edit. Skips still return 0. See `docs/chezmoi-apply-unmodified.md`.

## Sub-features

- `unmodified-apply` brings an untouched, outdated target up to date.
- `unmodified-skip-edit` reports and preserves a locally edited target.
- `unmodified-skip-delete` reports a locally deleted target and leaves it deleted.
- `unmodified-single` with `-- /abs/target` handles one file only.

## How to get to it (user POV)

- After an approved merge, run `chezmoi-apply-unmodified` from any shell.
- Run `chezmoi-apply-unmodified --source /abs/checkout` to apply another checkout.

## Driving it with drive.py

Preconditions:

- A fresh run with an empty `chezmoi status`. Launch has recorded chezmoi's last-write history for every target.

- **Local edit and deletion.** Change two targets the way a user would, then run the helper. Run `"$S/drive.py" "$RUN" --shell bash --label bash-apply-unmodified 'cmd:echo "# local edit" >> ~/.vimrc' 'cmd:rm ~/.fdignore' 'cmd:chezmoi status' 'cmd:chezmoi-apply-unmodified' 'cmd:tail -n1 ~/.vimrc; test -e ~/.fdignore || echo FDIGNORE-ABSENT' 'cmd:chezmoi status'`. The first status shows `DA .fdignore` and `MM .vimrc`. The helper prints one `Skipped locally changed target:` line for each, and exits 0. `~/.vimrc` still ends with `# local edit`, `FDIGNORE-ABSENT` prints, and the final status is unchanged.
- **Outdated target applied.** Edit a source file in the checkout (the change under test), then run `"$S/drive.py" "$RUN" --shell bash --label bash-apply-unmodified-outdated 'cmd:chezmoi status' 'cmd:chezmoi-apply-unmodified' 'cmd:chezmoi status'`. The first status lists the target. The helper prints no skip line for it, and the target drops out of the final status.
- **Proof.** Keep both `.json` files. Status before, helper output, and status after are the proof. Confirm the preserved edit with `"$S/in-run" "$RUN" tail -n1 .vimrc` (in-run starts in `$RUN/work`, so give paths from `~` inside a `sh -c`).

## Gotchas

- `chezmoi status` inside the run depends on launch's scaffolding exclusions. A run made some other way tries to download externals and can hang for about 50 seconds on a GitHub 504.
- The outdated-target journey edits the checkout behind the source link. Revert that edit, or commit it as the task change. Never leave a stray edit in the checkout.
- The helper does not handle run scripts or directory removals. `.chezmoiremove` entries need a separate check.
- Restore edited targets before driving another feature in the same run: `"$S/in-run" "$RUN" chezmoi apply --force`.
