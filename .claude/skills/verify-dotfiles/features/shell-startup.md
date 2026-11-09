# Shell startup

Opening a terminal runs the applied startup files. Nushell (Herdr panes), Bash (`bash -l` logins and Claude Code's Bash tool), and Zsh each reach a working prompt, with the dotfiles' helpers resolving from `~/.config/my-scripts/bin` and the shared shortcuts defined.

## Sub-features

- `startup-nu` starts interactive Nushell with the starship prompt, the fastfetch greeting, `zellij ls`, and the daily upkeep box.
- `startup-bash` starts interactive Bash, login and non-login. Bash shows no upkeep box.
- `startup-zsh` starts interactive Zsh, with the daily upkeep box.
- `startup-path` makes `ls-by-time`, `dir-picker`, and `chezmoi-apply-unmodified` resolve inside the applied home.
- `startup-shortcuts` defines `c`, `l`, and `sl` in all three shells. In Nushell they are aliases. In Bash and Zsh, `c` and `l` are functions and `sl` is an alias.

## How to get to it (user POV)

- Open a Herdr pane. `herdr-shell` runs the first of `nu`, `zsh`, or `bash` it finds.
- Start a login shell with `bash -l`, as an SSH login does when Bash is the account's shell.
- Type `zsh` or `bash` in any shell.

## Driving it with drive.py

Preconditions:

- `"$S/doctor" "$RUN"` exits 0.

- **Nushell.** Run `"$S/drive.py" "$RUN" --shell nu --label nu-startup 'cmd:which ls-by-time dir-picker chezmoi-apply-unmodified | get path' 'cmd:scope aliases | where name in [c l sl] | select name expansion'`. All three paths are inside `$RUN/home/.config/my-scripts/bin/`. The aliases are `c` = `cl`, `l` = `ezam`, and `sl` = `l`.
- **Bash login.** Run `"$S/drive.py" "$RUN" --shell bash --login --label bash-startup 'cmd:shopt -q login_shell && echo LOGIN; type -t c l sl; command -v ls-by-time chezmoi-apply-unmodified; type ls | head -1'`. The output is `LOGIN`, then `function`, `function`, and `alias`. Both paths are inside `$RUN/home`, and ``ls is aliased to `eza -aF'``.
- **Zsh.** Run `"$S/drive.py" "$RUN" --shell zsh --timeout 60 --label zsh-startup 'cmd:whence -w c l sl; command -v ls-by-time chezmoi-apply-unmodified; ls ~/.cache/zsh-init'`. The output is `c: function`, `l: function`, and `sl: alias`, then two paths inside `$RUN/home`. The cache lists `atuin.zsh`, `brew.zsh`, `mise.zsh`, `starship.zsh`, and `zoxide.zsh`, among others.
- **Zsh home greeting.** Run `"$S/drive.py" "$RUN" --shell zsh --cwd "$RUN/home" --label zsh-greeting 'cmd:pwd'`. The startup output adds the fastfetch logo and `ZELLIJ:`, and on this host `zsh: gita: command not found...`.
- **Proof.** Run `grep -inE 'error|warning|not found|no such file' "$RUN"/evidence/{nu,bash,zsh}-startup.txt`. A fresh home prints no matching line in any shell, so every hit is a finding. Compare it with a baseline run of the merge destination to tell whether the change under test caused it.

## Gotchas

- The only expected warning is Nushell's `warning: cargo is not available`, and it appears only when `cargo` is missing from the inherited PATH. Zsh prints its errors in lowercase (`no such file or directory`), so filter case-insensitively.
- The daily upkeep box appears on every first start in a run, because a fresh home has no upkeep stamp for today. Nushell shows it only when `CLAUDE` is unset; the run environment leaves it unset.
- The first Zsh start fills `~/.cache/zsh-init` and takes 1 to 3 seconds here. Sheldon plugins load only where `sheldon` is installed, and it is not installed on this host. Elsewhere the first start may clone plugins over the network, so keep `--timeout 60`.
- The Zsh home greeting runs only when `$PWD` is `$HOME` and `ZELLIJ` is unset. Nushell's fastfetch and `zellij ls` run in every directory.
- Herdr hooks stay off because the run has no `HERDR_*` variables, and drives never start `herdr-shell`. Prove Herdr integration in a live pane, outside this skill.
