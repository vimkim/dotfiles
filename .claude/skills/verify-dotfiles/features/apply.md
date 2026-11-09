# Apply the dotfiles

Applying the checkout builds the user's home. Every managed file, symlink, and template target appears with the source's content and modes, retired targets disappear, and a second apply changes nothing.

## Sub-features

- `apply-fresh` builds a home from an empty directory.
- `apply-templates` renders the five templates, and `~/.claude/CLAUDE.md` equals `dot_codex/AGENTS.md`.
- `apply-converge` leaves `chezmoi status` and `chezmoi diff` empty, and a second apply prints nothing.
- `apply-remove` deletes the retired targets that `.chezmoiremove` lists.
- `apply-edit` carries a source edit into its target on the next apply.

## How to get to it (user POV)

- Run `chezmoi apply` on a machine, as the README's setup steps do.
- After a merge, run `chezmoi-apply-unmodified`. See [apply-unmodified](./apply-unmodified.md).
- Review a pending change with `chezmoi diff`. `chzdiff` pipes it into the diffnav TUI in Nushell and Zsh; Bash has no `chzdiff`.

## Driving it with drive.py

Preconditions:

- A fresh run. `"$S/launch"` itself performs `apply-fresh`.

- **Fresh apply.** Launch. Run `RUN=$("$S/launch" | tail -n1)`. Exit 0 and `launch: ready (N files, ...)`. `wc -c < "$RUN/evidence/launch-verify.log"` prints `0`.
- **Converged.** Ask chezmoi in an interactive shell. Run `"$S/drive.py" "$RUN" --shell nu --label nu-apply-converge 'cmd:^chezmoi status' 'cmd:^chezmoi diff | lines | length' 'cmd:^chezmoi apply --exclude=externals --verbose | lines | length'`. The status output is empty, and both counts are `0`. `"$S/in-run" "$RUN" sh -c 'test -e ~/gh || echo NO-GH'` prints `NO-GH`, which shows that no install script ran.
- **Templates.** Run `"$S/in-run" "$RUN" sh -c 'cmp ~/.claude/CLAUDE.md ~/.local/share/chezmoi/dot_codex/AGENTS.md && chezmoi managed --include=templates'`. Exit 0, and the list is exactly `.claude/CLAUDE.md`, `.codex/hooks.json`, `.config/nushell/autoload/deeptutor.nu`, `.profile`, and `.zshenv`.
- **Removal.** Recreate two retired targets, then apply. Run `"$S/in-run" "$RUN" sh -c 'touch ~/.config/my-scripts/bin/lzps ~/.config/my-scripts/bin/gh-pr-view; chezmoi status; chezmoi apply --exclude=externals; ls ~/.config/my-scripts/bin/lzps ~/.config/my-scripts/bin/gh-pr-view'`. Status shows ` D .config/my-scripts/bin/gh-pr-view` and ` D .config/my-scripts/bin/lzps`. After apply, `ls` reports both missing.
- **Source edit.** Edit the checkout file under test, then run `"$S/in-run" "$RUN" chezmoi diff` and `"$S/in-run" "$RUN" chezmoi apply --exclude=externals`. The diff shows exactly the intended change, and `"$S/doctor" "$RUN"` passes again.
- **Proof.** Read the changed target with `"$S/in-run" "$RUN" sh -c 'cat ~/<target>'`. The content matches the edit.

## Gotchas

- Install scripts are no-ops in a run, and externals are excluded. So `~/gh/docserve`, `~/gh/herdr-next-to-current`, `~/gh/dirpick`, and `~/.config/zellij/plugins/*.wasm` are absent, and `~/.config/my-scripts/share/serve-html` is a dangling symlink. `~/.codex/hooks.json` names `~/.codex/herdr-agent-state.sh`, which this source does not provide. All of this is expected in a run.
- Launch applies the working tree. A checkout with git-ignored files deploys them as well: the main checkout deploys `~/.config/my-scripts/__pycache__/*.pyc` and `~/.claude/skills`, and a clean worktree does not. Compare `chezmoi --source <checkout> managed` between the two checkouts when a file count looks off.
- chezmoi itself skips every dot-prefixed source entry, such as the skill folder `.claude/` and `.git`. `.chezmoiignore` adds `README.md`, `docs/`, `tests/`, `tools`, and the root guidance files. `useful-patch/` is not ignored, so `~/useful-patch` deploys.
- `create_private_dot_gitconfig.local` writes `~/.gitconfig.local` only when it is missing. Later source edits leave an existing file unchanged.
- No pager is configured, so `chezmoi diff` prints straight to the transcript.
