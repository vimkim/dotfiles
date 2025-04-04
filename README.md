# vimkim's dotfiles

A reminder of how to set up my dotfiles on a new machine.

## Step 1: Install Zsh

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

## Step 2: Install Nix Package Manager

```bash
# ssh <(curl -L https://nixos.org/nix/install) --daemon
```

> nix recommended

or,

```bash
sh <(curl -L https://nixos.org/nix/install) --no-daemon
```

> personal choice, especially inside a container

```bash
. $HOME/.nix-profile/etc/profile.d/nix.sh

nix --extra-experimental-features nix-command --extra-experimental-features flakes profile install nixpkgs#chezmoi
```

Optionally (I do not recommend because sometimes locale breaks),

```bash
# nix --extra-experimental-features nix-command --extra-experimental-features flakes profile install nixpkgs#zsh
```

Note: nix-command and flakes are automatically enabled with chezmoi apply.

```bash
 # github handle after --apply
chezmoi init --apply vimkim
```

## Step 3: Install oh-my-zsh

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
mv .zshrc.pre-oh-my-zsh .zshrc
```

## Step 4: Other nix packages

This might take some time and disk spaces.

```bash
my-nix-install.sh
```

## Step 5: Install nvim dotfiles

```bash
cd $HOME/.config
git clone https://github.com/vimkim/nvim
```
