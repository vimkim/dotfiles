---
name: verify-dotfiles
description: Prove a change to this chezmoi dotfiles checkout works the way the user meets it. It applies the checkout into a disposable home, drives real Nushell, Bash, and Zsh sessions in a pseudo-terminal, and keeps the transcripts. Use before merging a change to shell startup files, helper scripts, chezmoi templates, or ignore rules. Also use to reproduce or demonstrate dotfiles behavior without touching the live home.
---

# Verify dotfiles

The product is the home that `chezmoi apply` builds from this checkout, used through interactive shells. Herdr panes start `herdr-shell`, which runs `nu` first, so Nushell is the primary surface. Bash is the login shell, and Zsh is still supported. Every run gets its own disposable home. The live home and the live Herdr session stay untouched.

```bash
S=<checkout>/.claude/skills/verify-dotfiles/scripts   # every helper below; each explains itself in its header
```

## 1. Launch

```bash
RUN=$("$S/launch" | tail -n1)
```

- Launch applies the checkout that holds this skill into `$RUN/home`. Use `--source DIR` to apply another checkout, such as the merge destination for a baseline.
- Ready means exit 0 and the stderr line `launch: ready (...)`: `chezmoi verify` agreed with the source, so the home is usable. It takes about 3 seconds.
- Runs live in `${TMPDIR:-/tmp}/verify-dotfiles/<run-id>/`; `VERIFY_DOTFILES_ROOT` moves them. Launch refuses a root inside the live home: mise and direnv read config from every ancestor of the working directory, so a run under `~` reads `~/.config/mise/config.toml`. Runs share nothing except the checkout, so several can run side by side.
- The run is a fresh machine. `$RUN/home/.local/share/chezmoi` links to the checkout, and `~/.config/chezmoi/chezmoi.toml` comes from `chezmoi init`. Plain `chezmoi` and `chezmoi-apply-unmodified` work inside the run with no flags. Writes through the link (`chezmoi add`, `chez-add`, `chezmoi edit`) change the checkout.
- Scaffolding: launch appends `exclude = ["scripts", "externals"]` for apply, diff, status, and verify to the run's chezmoi config. Run scripts clone repos and install tools; externals download zellij plugins from GitHub and can hang on a 504.
- After editing the checkout, re-apply with `"$S/in-run" "$RUN" chezmoi apply`.
- On failure, launch prints the tail of `$RUN/evidence/launch-*.log` and exits 1. Run cleanup on that run too.

## 2. Doctor

```bash
"$S/doctor" "$RUN"
```

Doctor is read-only. Run it first, and again whenever a result surprises you. It checks these, and exit 0 means the run is worth driving:

- Isolation: HOME is the disposable home, `run.env` has no live-session variables (`XDG_*`, `HERDR_*`, `ATUIN_*`), and PATH excludes the live `~/.config/my-scripts/bin`.
- The source link and the checkout HEAD compared with launch time.
- Freshness: `chezmoi verify` against the current source, uncommitted edits included. A FAIL after editing the checkout means re-apply.
- Live processes this run started, and the tools that drives need.

## 3. Drive

Both entry points start from the run's scrubbed environment (`$RUN/run.env`) with HOME set to the disposable home.

- `"$S/drive.py" "$RUN" --shell nu|bash|zsh --label NAME [--cwd DIR] [--login] STEP...` types into an interactive shell. This is the user path.
- `"$S/in-run" "$RUN" COMMAND...` runs one non-interactive command. Use it for setup and for reading side effects (`chezmoi status`, a target file). It is not proof of interactive behavior.

Steps run in order:

- `cmd:TEXT` enters a command line as one bracketed paste, presses Enter, waits for the next prompt, and records the exit status. Nushell updates the status only after an external command or an error.
- `keys:TEXT` types raw keys with escapes such as `\r`, `\x1b`, `\t`, `\x03`, and `\x1b[B`. Use it for fzf pickers and other full-screen programs.
- `expect:REGEX` waits until the screen text since the last checkpoint matches.
- `sleep:SECS` waits.

The driver types a line only after the line editor turns on bracketed paste (`ESC[?2004h`), which reedline, readline, and zle do once per prompt. Reedline discards typed-ahead keys, so this wait keeps input intact. A `cmd` step after `keys` steps first waits for the prompt to return. Use `cmd` for commands that return to the prompt, and use `keys` plus `expect` for anything interactive.

Drives start in `$RUN/work`. Starting in `$RUN/home` also runs the Zsh home greeting (fastfetch, `gita ll`, `zellij ls`), so start there only when the greeting is under test.

Before driving a feature, read [`features/README.md`](features/README.md) and the matching feature file.

## 4. Evidence

Each drive writes three files in `$RUN/evidence/`:

- `<label>.txt` is flattened screen text. Every drawn row stays, overwritten text included.
- `<label>.json` records each step's result, exit status, output, and duration, plus the shell's exit and whether the driver killed it.
- `<label>.typescript` holds the raw terminal bytes for exact rendering.

Launch writes `launch-{init,apply,verify}.log` there, and `$RUN/run.json` records the source, commit, dirty path count, and chezmoi version.

Proof standards:

- Drive the real user path: a typed command in an interactive shell started from the applied home. Sourcing a script in isolation or calling a helper's internals proves less.
- Capture the action and the resulting state: the step that acts, then a step that reads the result, such as the cwd after `c` or a target's content after apply.
- Check side effects alongside the screen: files in `$RUN/home`, `chezmoi status`, and `which <helper>` resolving inside `$RUN/home`.
- A drive PASS means every step finished. Judge the JSON statuses and outputs against the feature's proof before you call the feature verified.
- Judge startup noise against a baseline: launch a second run with `--source <merge-destination checkout>` and compare startup outputs.
- Report the run path, the commit from `run.json`, the feature IDs driven, the evidence files, and each mapped entry point you skipped, with its reason.

## 5. Cleanup

```bash
"$S/cleanup" "$RUN" && ls "$RUN/evidence"
```

Cleanup stops only processes whose environment carries this run's `VERIFY_DOTFILES_RUN` marker. It removes the source link first, then the home, `work/`, and `run.env`. `evidence/` and `run.json` stay. Run it after every run, failed ones included, then confirm the evidence listing. Delete old run directories only when the user asks.

## Not driven by this skill

- Run scripts (`.chezmoiscripts`) and externals: their unit tests are `tests/test_install_*.py` and `tests/test_html_serve_migration.py`.
- Herdr itself (`private_dot_config/herdr/config.toml`): the run has no Herdr server, and the scrubbed environment turns off the shells' Herdr hooks.
- GUI terminals (WezTerm, kitty, Alacritty): this host has slow X11 forwarding, so never launch GUI programs.
- Helpers that need network or credentials (`daily-update` upgrades, `gh-*`, `claude-account`).

Report each one a change touches as not driven, and name the unit tests you ran instead (`python3 -m unittest discover -s tests -p 'test_<area>*.py'`).
