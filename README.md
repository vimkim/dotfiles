# vimkim's dotfiles

A reminder of how to set up my dotfiles on a new machine.

## Step 1: Install Homebrew

Prerequisite on Ubuntu (e.g. a fresh Docker container) — the Homebrew installer needs `curl` and `git`:

```bash
sudo apt install curl git
```

Follow the instructions at <https://brew.sh/>:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

After installing, if you want to use brew one time only (without polluting your rc files), load it into the current shell (Linux):

```bash
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv bash)"
```

> On macOS, use `eval "$(/opt/homebrew/bin/brew shellenv bash)"` instead.

<details>
<summary>Alternative: Nix Package Manager</summary>

```bash
sh <(curl --proto '=https' --tlsv1.2 -L https://nixos.org/nix/install)
```

or,

```bash
sh <(curl --proto '=https' --tlsv1.2 -L https://nixos.org/nix/install) --no-daemon
```

> personal choice, especially inside a container

```bash
. $HOME/.nix-profile/etc/profile.d/nix.sh
```

Note: nix-command and flakes are automatically enabled with chezmoi apply.

</details>

## Step 2: Install zsh, chezmoi, and nushell, then apply dotfiles

```bash
brew install zsh chezmoi nushell
```

> Note: the package is `nushell`, not `nu`.

<details>
<summary>Alternative: zsh via system package manager</summary>

#### Arch

```bash
sudo pacman -S zsh
```

#### RHEL (Fedora, Rocky, CentOS)

```bash
sudo dnf install zsh
```

#### Ubuntu

```bash
sudo apt install zsh
```

</details>

<details>
<summary>Alternative: chezmoi via Nix</summary>

```bash
nix --extra-experimental-features nix-command --extra-experimental-features flakes profile install nixpkgs#chezmoi
```

</details>

Then apply:

```bash
# github handle after --apply
chezmoi init --apply vimkim
```

### Updating on an existing machine

`chezmoi init --apply` only clones when the source directory does not exist
yet; it does not pull remote updates. To sync a patch made on another machine,
either pull-and-apply in one step:

```bash
chezmoi update
```

or, when the machine might have local edits worth checking first:

```bash
chezmoi git pull -- --autostash --rebase   # just pull the source repo
chezmoi diff                               # see what apply would change
chezmoi apply                              # apply when happy
```

### Prerequisites for config.nu

None of these are hard requirements — config.nu quietly skips every tool that
is not installed. Recommended for the interactive experience (prompt, history,
completions; without carapace, Tab-completion for external commands does not
work):

```bash
brew install starship atuin carapace
```

<details>
<summary>Optional tools</summary>

Optional tools used by aliases and helper commands (e.g. eza for `l`,
fzf/fd/ripgrep for the pickers, lazygit for `lz`, delta as the git/lazygit
pager):

```bash
brew install eza fzf fd ripgrep lazygit delta
```

Misc dependencies:

```bash
brew install mise direnv zoxide fastfetch diffnav gh
```

The terminal configuration uses Maple Mono. On Fedora, follow
[Installing Maple Mono Nerd Font](docs/maple-mono-nerd-font.md).

</details>

### Shared shell shortcuts

Interactive Bash and Zsh load `~/.config/my-scripts/shell/productivity.sh`.
These everyday shortcuts also exist in Nushell:

| Command | Behavior |
| --- | --- |
| `c`, `i` | Pick a directory with `dir-picker`, then list its contents. |
| `c DIR` | Change directly to DIR, then list its contents. |
| `c [DIR] --query TEXT` | Browse DIR (current directory by default) with an initial name query. |
| `l`, `sl` | Detailed eza grid with hidden entries, icons, Git state, and modification-time sorting. |
| `ll` | Detailed eza rows with owners and permissions. |
| `h`, `up`, `back` | Go to the parent or previous directory and list it. |
| `mc DIR` | Create a directory, including parents, and enter it. |
| `gr`, `gcd`, `pr`, `pcd` | Go to the Git repository root and list it. |
| `cz` | Open zoxide's interactive directory picker (`zi`). |
| `ch` | Pick a previously visited directory from the shared directory history. |
| `ch --forget`, `ch --delete`, `ch --prune` | Forget selected entries, confirm moving selected directories to trash, or prune missing paths. |
| `chf`, `chd`, `chp`, `vh` | Shortcuts for forget, trash, prune, and viewing history. |
| `n`, `na` | Pick a Just recipe from `./justfile` or `~/.config/my-scripts/justfile`. |
| `nr`, `nc` | Pick from `$MY_CUBRID/remote-nu.just` or `$MY_CUBRID/cubrid-justfiles/justfile` (`MY_CUBRID` defaults to `~/my-cubrid`). |
| `fp [QUERY]` | Print a selected file's path using `file-picker.sh`. |
| `cf [QUERY]` | Enter the directory containing a selected file. |
| `vc [QUERY]` | Edit a selected file from the current directory. |
| `y` | Run Yazi and enter its exit directory. |
| `fzfm`, `fda`, `rgall` | Fuzzy finder, fd including hidden/ignored files, and ripgrep including hidden/ignored files. |
| `conf`, `confd`, `mycub`, `nvimh` | Jump to configuration, CUBRID, or Neovim directories. |
| `lz`, `lj`, `lzd`, `v`, `py`, `sctl` | Lazygit, lazyjj, lazydocker, Neovim, Python 3, and systemctl. |
| `lzps` (`lzp` in Zsh/Nushell) | Run lazydocker with sudo against the system Podman socket. |
| `ports`, `ports-tcp`, `ports-all` | Existing port listing helper, its TCP view, or somo. |

`cd` retains its existing change-and-list behavior; bare `cd` goes home.
`l` and `ll` fall back to system `ls` when eza is unavailable. Pickers require
the existing managed `dir-picker` / `file-picker.sh` commands and their
dependencies (Python 3, fzf, and, for files, fd/eza). Cancelling a picker leaves
the current directory unchanged. Other shortcuts require their named tools;
they do not install them during shell startup.

`lzps` resolves lazydocker from the caller's `PATH` before invoking sudo, then
passes its absolute path and `DOCKER_HOST=unix:///run/podman/podman.sock` to sudo.
It forwards all arguments and requires only `sh`, sudo, and lazydocker on `PATH`;
it has no Nix or Homebrew dependency. `lzd` runs lazydocker without sudo.

The Just pickers prepare an editable command: Zsh preloads the next prompt;
Bash opens a `Run:` Readline prompt where Enter runs the command and records it
in history. Noninteractive Bash prints the prepared command. They use the existing
`just-pick-and-print.nu` helper and require Nushell, Just, and fzf.
Directory history uses the shared Python `dir-history` command and a SQLite
database under `${XDG_STATE_HOME:-$HOME/.local/state}/dir-history/`. Bash records
directory changes before each prompt; Zsh and Nushell record them on directory
changes. The existing JSON history is imported once and left unchanged.
See [directory history](docs/directory-history.md) for commands, concurrency,
migration, and reloading existing sessions.

### Listing helpers

`ls-by-size`, `ls-by-name`, and `ls-by-time` provide detailed eza listings sorted
largest first, alphabetically, and newest first. `ls-by-extension`, `ls-tree`,
`ls-dirs`, and `ls-files` add extension sorting, a two-level tree, and filtered
views. All include hidden entries and accept paths and eza options.

In a terminal, long output opens in less; short output stays visible. Use
`--no-pager` to print directly and `--reverse` to reverse the default order.
Pipes and redirected output bypass paging. These Python 3 scripts work in
Nushell, Bash, and Zsh; see [usage and verification](docs/ls-helper-family.md).

### Handoff directory

Run `handoff-dir` to create `.handoff/` in the current directory and write `*`
to `.handoff/.gitignore`, ignoring everything inside. The Python 3 command lives
in `~/.config/my-scripts/bin`; running it again preserves the directory's other
contents and rewrites its `.gitignore`.
It reports `Created: .handoff/` or `Already exists: .handoff/` after completing
successfully.

### Apply dotfiles while preserving local changes

`chezmoi-apply-unmodified` (in `~/.config/my-scripts/bin`) applies managed files
and symlinks while reporting locally changed targets as successful skips.
Use `--source /absolute/source/checkout` to process all managed files and symlinks
from a particular checkout. See [usage and verification](docs/chezmoi-apply-unmodified.md).

### HTML review from a remote server

`~/.config/my-scripts/bin/serve-html.py` serves an HTML directory until Ctrl+C,
prefers memorable four-digit free ports, and prints Tailscale/VPN and LAN links
for opening from your PC. See [usage and verification](docs/serve-html.md).

### Daily AI-toolchain upkeep

`daily-update` (in `~/.config/my-scripts/bin`) upgrades Codex, Claude Code, and
the globally installed agent skills in one go:

```bash
daily-update            # run everything, report stale skills, mark today done
daily-update --status   # show current versions and whether today is done
daily-update --stale    # list stale skills, changing nothing
daily-update --prune    # delete the stale skills that --stale listed
daily-update --reset    # clear today's mark so the reminder comes back
```

Both `config.nu` and `.zshrc` call `daily-update --remind` at the end of
interactive startup. That prints a pending block on *every* new shell and keeps
printing until `daily-update` actually runs; the run writes today's date to
`~/.cache/daily-update.stamp`, which silences the reminder for the rest of the
calendar day. Seeing the reminder never dismisses it, which is the difference
from the PR digest above.

The stamp records that a run happened, not that every step succeeded. A failed
step is listed at the end of the run and left for a deliberate re-run, so a
network blip cannot trap the reminder in a loop.

Skills come from the `skills` CLI and are tracked in `~/.agents/.skill-lock.json`.
Because `~/.claude/skills/*` symlinks into `~/.agents/skills`, the single
`skills update --global` covers both Claude Code and Codex.

#### Pruning stale skills

`skills update` never removes anything, and the CLI has no prune command, so a
skill deleted from its source repository stays installed and active forever.
Each run therefore reports what has gone stale and points at `--prune`. The
startup reminder then names those skills, reading them from cache so it stays
offline and fast; past eight names it summarises the remainder as a count.

A skill is stale only if the lock file claims it *and* one of these holds:

- it no longer exists in its source repository,
- its directory under `~/.agents/skills` is gone, or
- its `~/.claude/skills` symlink is broken.

Everything else is left alone. This matters because the lock file records only
GitHub-sourced installs: the whole `my-cubrid-skills` collection is installed
from a local path and never appears in it, so treating the lock as an allowlist
would delete every personal skill. Names present in `~/gh/my-cubrid-skills` are
additionally protected even if a source repo later publishes the same name.

Two failure modes are guarded explicitly. A `gh` failure is never read as "the
repository is empty", and because `gh api` prints its 404 body to stdout, the
upstream list is accepted only when the command succeeds *and* every line looks
like a bare directory name. `--prune` moves what it removes into
`~/.cache/daily-update/trash/<timestamp>/`, with a copy of the lock file, rather
than deleting outright.

Upgrades always resolve `~/.local/bin` first rather than trusting the calling
shell's PATH, because the two disagree on this host: zsh finds a mise-managed
npm `codex` and a stale root-owned `/usr/bin/claude` (npm global, 2.0.25) that
the nushell login shell never sees. Without the pin, running `daily-update`
from zsh would upgrade a different install than the one you actually use.

### WezTerm on Fedora KDE through Herdr

The display-environment, XKB layout, and `dead_hamza` packaging diagnosis is
recorded in [WezTerm on Fedora KDE through Herdr](docs/wezterm-fedora.md),
including verification and rollback commands.

Herdr's tab agent markers, workspace tab inventory, and updater controls are
documented in [Herdr tab agent indicators](docs/herdr-tab-status.md).

### Optional: Install the Colemak programmer layout

The KDE Wayland configuration includes a standalone Colemak layout with
programming symbols on the unshifted number row. Follow
[Installing the Colemak Programmer Layout](docs/colemakp.md) to validate and
apply it without shadowing the system US XKB symbols file.

<details>
<summary>Optional Step: Install oh-my-zsh</summary>

I now use nushell instead, by the way.

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
mv .zshrc.pre-oh-my-zsh .zshrc
```

</details>

<details>
<summary>Optional Step: Other nix packages</summary>

Only if you installed Nix. This might take some time and disk spaces.

```bash
my-nix-install.sh
```

</details>

## Step 3: Install nvim dotfiles

```bash
cd $HOME/.config
git clone https://github.com/vimkim/nvim
```

## Step 4: X11 Forwarding

```bash
sudo dnf install xauth
sudo apt install xauth
sudo pacman -S xorg-xauth
```

```bash
# /etc/ssh/sshd_config
X11Forwarding yes
X11DisplayOffset 10
X11UseLocalhost yes
```

## Daily tool and personal collection upkeep

See [daily-update](docs/daily-update.md) for refresh policy, partial results,
third-party boundaries, and isolated verification.
