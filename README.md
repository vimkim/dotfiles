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

## Step 2: Install Zsh

```bash
brew install zsh
```

<details>
<summary>Alternatives (Arch, RHEL, Ubuntu)</summary>

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

## Step 3: Install chezmoi and nushell, then apply dotfiles

```bash
brew install chezmoi nushell
```

> Note: the package is `nushell`, not `nu`.

<details>
<summary>Alternative: with Nix</summary>

```bash
nix --extra-experimental-features nix-command --extra-experimental-features flakes profile install nixpkgs#chezmoi
```

</details>

Then apply:

```bash
# github handle after --apply
chezmoi init --apply vimkim
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

</details>

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

## Step 4: Install nvim dotfiles

```bash
cd $HOME/.config
git clone https://github.com/vimkim/nvim
```

## Step 5: X11 Forwarding

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
