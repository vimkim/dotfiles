#!/bin/bash

# Array of packages to install
packages=(
    asdf
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
    lnav
    mdbook
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
