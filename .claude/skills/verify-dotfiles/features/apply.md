# Apply the dotfiles

Applying the checkout builds the user's home: every managed file, symlink, and template target appears with the source's content and modes, and a second apply changes nothing.

## Sub-features

- `apply-fresh` builds a home from an empty directory.
- `apply-templates` renders templates. For example, `~/.claude/CLAUDE.md` equals `dot_codex/AGENTS.md`.
- `apply-converge` leaves `chezmoi status` empty and makes a second apply a no-op.
- `apply-edit` carries a source edit into its target on the next apply.

## How to get to it (user POV)

- Run `chezmoi apply` on a machine, as the README's setup steps do.
- After a merge, run `chezmoi-apply-unmodified`. See [apply-unmodified](./apply-unmodified.md).
- Review a pending change with `chezmoi diff` (or the `chzdiff` alias).

## Driving it with drive.py

Preconditions:

- A fresh run. `"$S/launch"` itself performs `apply-fresh`.

- **Fresh apply.** Launch. Run `RUN=$("$S/launch" | tail -n1)`. Exit 0 and `launch: ready (N files, ...)`. `$RUN/evidence/launch-verify.log` is empty.
- **Converged.** Ask chezmoi in the run's interactive shell. Run `"$S/drive.py" "$RUN" --shell nu --label nu-apply-converge 'cmd:^chezmoi status' 'cmd:^chezmoi diff | lines | length'`. The status output is empty, and the diff line count is `0`.
- **Templates.** Compare a rendered target with its source. Run `"$S/in-run" "$RUN" sh -c 'cmp ~/.claude/CLAUDE.md ~/.local/share/chezmoi/dot_codex/AGENTS.md && chezmoi managed --include=templates'`. Exit 0, and the list contains `.claude/CLAUDE.md`, `.codex/hooks.json`, `.profile`, and `.zshenv`.
- **Source edit.** Edit the checkout file under test, then re-apply. Run `"$S/in-run" "$RUN" chezmoi diff` before and `"$S/in-run" "$RUN" chezmoi apply` after. The diff shows exactly the intended change, and `"$S/doctor" "$RUN"` passes again.
- **Proof.** Read the changed target. Run `"$S/in-run" "$RUN" cat ~/<target>`; inside in-run, `~` is the disposable home. The content matches the edit.

## Gotchas

- Run scripts and externals are excluded, so `~/.config/zellij/plugins/*.wasm`, `~/gh/docserve`, and `~/gh/herdr-next-to-current` are absent. That absence is expected in a run, not a regression.
- In the agent's own shell, `~` is the live home. Expand `~` inside `in-run` or a drive only.
- `.chezmoiignore` decides what is deployed. `README.md`, `docs/`, `tests/`, and every dot-prefixed source entry (including `.claude/`) never reach the home.
- `chezmoi diff` uses the pager configured in the run. Pipe it to `cat` or count lines for a clean transcript.
