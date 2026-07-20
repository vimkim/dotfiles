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

### Alternative: Nix Package Manager

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

## Step 2: Install Zsh

```bash
brew install zsh
```

### Alternatives

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

## Step 3: Install chezmoi and nushell, then apply dotfiles

```bash
brew install chezmoi nushell
```

> Note: the package is `nushell`, not `nu`.

### Alternative: with Nix

```bash
nix --extra-experimental-features nix-command --extra-experimental-features flakes profile install nixpkgs#chezmoi
```

Then apply:

```bash
# github handle after --apply
chezmoi init --apply vimkim
```

### Prerequisites for config.nu

The nushell config expects a couple of tools to be around. Starship is the
only hard requirement (the prompt is initialized unconditionally), and atuin
and carapace are used for history and completions:

```bash
brew install starship atuin carapace
```

The rest are optional — config.nu quietly skips them when they are not
installed:

```bash
brew install zoxide eza mise direnv fzf fd ripgrep
```

## Optional Step: Install oh-my-zsh

I now use nushell instead, by the way.

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
mv .zshrc.pre-oh-my-zsh .zshrc
```

## Step 4: Other nix packages

Only if you installed Nix. This might take some time and disk spaces.

```bash
my-nix-install.sh
```

## Step 5: Install nvim dotfiles

```bash
cd $HOME/.config
git clone https://github.com/vimkim/nvim
```

## Step 6: X11 Forwarding

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
