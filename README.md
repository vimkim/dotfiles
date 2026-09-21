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

### Daily AI-toolchain upkeep

`daily-update` (in `~/.config/my-scripts/bin`) upgrades Codex, Claude Code, and
the globally installed agent skills in one go:

```bash
daily-update            # run everything, then mark today done
daily-update --status   # show current versions and whether today is done
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

Upgrades always resolve `~/.local/bin` first rather than trusting the calling
shell's PATH, because the two disagree on this host: zsh finds a mise-managed
npm `codex` and a stale root-owned `/usr/bin/claude` (npm global, 2.0.25) that
the nushell login shell never sees. Without the pin, running `daily-update`
from zsh would upgrade a different install than the one you actually use.

### WezTerm on Fedora KDE through Herdr

The display-environment, XKB layout, and `dead_hamza` packaging diagnosis is
recorded in [WezTerm on Fedora KDE through Herdr](docs/wezterm-fedora.md),
including verification and rollback commands.

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
