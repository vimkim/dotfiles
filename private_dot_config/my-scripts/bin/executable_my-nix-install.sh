#!/bin/bash

# TIP: it is not a good idea to use nix profile install zsh.
# Sometimes, in RHEL based distros, zsh-autocompletion won't work properly in nix zsh.
# due to locale not being properly set. I suspect this issue arises from en_US.utf8 vs. en_US.UTF-8.

# Array of packages to install
packages=(
    gum
    gnum4
    astyle
    atuin
    bandwhich
    zellij
    zoxide
    bat
    binsider
    broot
    btop
    ccache
    cgdb
    clang-tools
    cmake
    croc
    delta
    diffnav
    diffstat
    direnv
    du-dust
    dua
    eza
    fastfetch
    fd
    flex
    fzf
    gdb
    gh
    git
    git-extras
    gita
    helix
    hexyl
    htop
    jq
    just
    lazydocker
    lazygit
    mdbook
    mise
    navi
    neovim
    nethogs
    netscanner
    ninja
    procs
    ripgrep
    sheldon
    starship
    stow
    tealdeer
    television
    termshark
    trash-cli
    trippy
    tt
    yazi
)

# Function to install a package
install_package() {
    local package=$1
    echo "Installing $package..."
    nix profile install "nixpkgs#$package"
}

# Main execution
echo "Starting package installation..."
echo "Total packages to install: ${#packages[@]}"
echo

# Install packages
for package in "${packages[@]}"; do
    install_package "$package"
done

echo
echo "Installation complete!"
