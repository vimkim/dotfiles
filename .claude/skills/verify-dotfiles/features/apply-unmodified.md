# Apply only unmodified targets

`chezmoi-apply-unmodified` is how merged changes reach the home. It applies every file and symlink that is unchanged since chezmoi last wrote it. It skips a locally edited or deleted target with `Skipped locally changed target: <path>`, and an existing target with no last-write history with `Skipped pre-existing target without last-write state: <path>`. Either way it keeps the user's file, and skips still return 0. See `docs/chezmoi-apply-unmodified.md`.

## Sub-features

- `unmodified-apply` brings an untouched, outdated target up to date.
- `unmodified-skip-edit` reports and preserves a locally edited target.
- `unmodified-skip-delete` reports a locally deleted target and leaves it deleted.
- `unmodified-single` with `-- /abs/target` handles that one file only.
- `unmodified-preexisting` reports and preserves an outdated target that has no last-write history.

## How to get to it (user POV)

- After an approved merge, run `chezmoi-apply-unmodified` from any shell.
- Run `chezmoi-apply-unmodified -- /abs/target` for one file, or `--source /abs/checkout` to apply another checkout.

## Driving it with drive.py

Preconditions:

- A fresh run with an empty `chezmoi status`. Launch has recorded chezmoi's last-write history for every target.
- The helper is on PATH only in drive shells, so drive it with `drive.py`, not `in-run`.

- **Local edit and deletion.** Run `"$S/drive.py" "$RUN" --shell bash --label bash-apply-unmodified 'cmd:chezmoi status' 'cmd:echo "# local edit" >> ~/.vimrc' 'cmd:rm ~/.fdignore' 'cmd:chezmoi status' 'cmd:chezmoi-apply-unmodified' 'cmd:tail -n1 ~/.vimrc; test -e ~/.fdignore || echo FDIGNORE-ABSENT' 'cmd:chezmoi status'`. The first status is empty. The second shows `DA .fdignore` and `MM .vimrc`. The helper prints one `Skipped locally changed target: $RUN/home/...` line for each, `.fdignore` first, and exits 0. `# local edit` and `FDIGNORE-ABSENT` print, and the final status is unchanged.
- **Restore.** Run `"$S/in-run" "$RUN" chezmoi apply --force --exclude=externals`. `"$S/in-run" "$RUN" chezmoi status` is empty again.
- **Single target.** Append `# probe` to `dot_xprofile` and `dot_bash_profile` in the checkout. Run `"$S/drive.py" "$RUN" --shell bash --label bash-apply-unmodified-single 'cmd:chezmoi status' 'cmd:chezmoi-apply-unmodified -- ~/.xprofile' 'cmd:chezmoi status' 'cmd:grep -c "# probe" ~/.xprofile ~/.bash_profile'`. The first status shows ` M .bash_profile` and ` M .xprofile`. The helper prints nothing. Only ` M .bash_profile` remains, and the counts are `.xprofile:1` and `.bash_profile:0`.
- **Outdated target.** Run `"$S/drive.py" "$RUN" --shell bash --label bash-apply-unmodified-outdated 'cmd:chezmoi status' 'cmd:chezmoi-apply-unmodified' 'cmd:chezmoi status' 'cmd:grep -c "# probe" ~/.xprofile ~/.bash_profile'`. The helper prints no skip line, the final status is empty, and both counts are `1`. Revert the probes with `git -C <checkout> checkout -- dot_xprofile dot_bash_profile`, then restore.
- **No last-write history.** Append `# probe` to `dot_xprofile` again. Run `"$S/drive.py" "$RUN" --shell bash --label bash-apply-unmodified-preexisting 'cmd:chezmoi state delete --bucket=entryState --key="$HOME/.xprofile"' 'cmd:chezmoi status' 'cmd:chezmoi-apply-unmodified' 'cmd:grep -c "# probe" ~/.xprofile'`. Status shows ` M .xprofile`. The helper prints `Skipped pre-existing target without last-write state: $RUN/home/.xprofile`, and the count is `0`. Revert the probe and restore.
- **Proof.** Keep every `.json`: status before, helper output, and status after are the proof.

## Gotchas

- `chezmoi status` prints paths relative to the home, and the skip lines print absolute paths. Match the skip lines on the path suffix.
- The helper only checks targets that differ from the source. Deleting the last-write history of a target that matches the source prints nothing.
- The probe journeys edit the checkout behind the source link. Revert every probe before committing. A stray probe in the checkout ships with the task.
- The helper passes only file and symlink include lists to chezmoi, so it never runs install scripts or downloads externals. It also skips `.chezmoiremove` entries; [apply](./apply.md) drives removals.
