# vimkim's dotfiles

A reminder of how to set up my dotfiles on a new machine.

## Installation

### Install zsh using distro package manager (Optional)

```bash
sudo apt install zsh

sudo dnf install zsh

sudo pacman -S zsh
```

### Install nix package manager

```bash
sh <(curl -L https://nixos.org/nix/install) --daemon

sh <(curl -L https://nixos.org/nix/install) --no-daemon

. /home/vimkim/.nix-profile/etc/profile.d/nix.sh

nix --extra-experimental-features nix-command --extra-experimental-features flakes profile install nixpkgs#zsh
nix --extra-experimental-features nix-command --extra-experimental-features flakes profile install nixpkgs#chezmoi
```

Note: nix-command and flakes are automatically enabled with chezmoi apply.

```
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
