# Shell startup

Opening a terminal runs the applied startup files. Nushell (Herdr panes), Bash (the login shell), and Zsh each reach a working prompt, with the dotfiles' helpers resolving from `~/.config/my-scripts/bin` and the shared shortcuts defined.

## Sub-features

- `startup-nu` starts interactive Nushell: the starship prompt, the fastfetch greeting, and the daily upkeep box when one is due.
- `startup-bash` starts interactive Bash, login and non-login.
- `startup-zsh` starts interactive Zsh.
- `startup-path` makes helpers such as `ls-by-time`, `dir-picker`, and `chezmoi-apply-unmodified` resolve inside the applied home.
- `startup-shortcuts` defines `c`, `l`, and `sl` in all three shells.

## How to get to it (user POV)

- Open a Herdr pane. `herdr-shell` runs `nu`.
- Log in over SSH, which starts a login Bash.
- Type `zsh` or `bash` in any shell.

## Driving it with drive.py

Preconditions:

- `"$S/doctor" "$RUN"` exits 0.

- **Nushell.** Open a shell and look up a helper. Run `"$S/drive.py" "$RUN" --shell nu --label nu-startup 'cmd:which ls-by-time dir-picker | get path'`. Startup is `ok`, and both paths are inside `$RUN/home/.config/my-scripts/bin/`.
- **Bash login.** Run `"$S/drive.py" "$RUN" --shell bash --login --label bash-startup 'cmd:shopt -q login_shell && echo LOGIN; type c | head -1; command -v ls-by-time'`. The output has `LOGIN` and `c is a function`, and the path is inside `$RUN/home`.
- **Zsh.** Run `"$S/drive.py" "$RUN" --shell zsh --label zsh-startup 'cmd:whence -w c l; command -v ls-by-time'`. `c` and `l` are reported, and the path is inside `$RUN/home`.
- **Proof.** Read each `<label>.json` startup step's `output` and list every line containing `error`, `warning`, `not found`, or `No such file`. Compare that list with the expected fresh-home messages below, and with a baseline run of the merge destination. A new message is a finding.

## Gotchas

- Expected fresh-home messages, also present on `main` (3e44812): Bash prints `~/.cargo/env: No such file or directory` (from `dot_bashrc:341`), and Zsh prints `no such file or directory: ~/my-cubrid/aliases.sh` (from `private_dot_config/my-scripts/zsh/aliases.zsh:755`). Nushell and Zsh print a `daily upkeep pending` box when `daily-update` has work.
- The first Zsh start takes about 3 seconds, because it fills the `~/.cache/zsh-init` cache and sheldon may clone plugins over the network. Later drives in the same run are faster. Give a first Zsh drive `--timeout 60` on a slow network.
- A Bash `ls` error looks like eza (`(os error 2)`), because `ls` is aliased to eza.
- Starting in `$RUN/home` makes Zsh run fastfetch, `gita ll`, and `zellij ls`. The default `$RUN/work` skips that greeting.
- Herdr hooks stay off because the run has no `HERDR_*` variables. Prove Herdr integration in a live pane, outside this skill.
