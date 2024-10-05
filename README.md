# vimkim's dotfiles

A reminder of how to set up my dotfiles on a new machine.

## Installation

### install zsh

```bash
sudo pacman -S zsh
zsh
```

### install oh-my-zsh (optional)

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
```

### install nix package manager

```bash
sh <(curl -L https://nixos.org/nix/install) --daemon

sh <(curl -L https://nixos.org/nix/install) --no-daemon
```

### install chezmoi

```bash
nix-env -iA nixpkgs.chezmoi
chezmoi init --apply vimkim
```

### install nvim dotfiles

```bash
cd $HOME/.config
git clone https://github.com/vimkim/nvim
```
