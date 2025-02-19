# vimkim's dotfiles

A reminder of how to set up my dotfiles on a new machine.

## Installation

### Install zsh using distro package manager (Optional)

#### Arch

```bash
sudo pacman -S zsh
```

#### Ubuntu

```bash
sudo apt install zsh
```

#### RHEL (Fedora, Rocky, Centos)

```bash
sudo dnf install zsh
```

### Install nix package manager

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

### Install oh-my-zsh

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
mv .zshrc.pre-oh-my-zsh .zshrc
```

### Other nix packages

```bash
my-nix-install.sh
```

### Install nvim dotfiles

```bash
cd $HOME/.config
git clone https://github.com/vimkim/nvim
```
