#!/bin/bash

# Array of packages to install
packages=(
    asdf
    astyle
    atuin
    bandwhich
    bat
    bind
    binsider
    bison
    broot
    btop
    ccache
    cgdb
    chezmoi
    clang-tools
    cmake
    croc
    delta
    diffnav
    diffstat
    direnv
    diskonaut
    du-dust
    dua
    entr
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
    gitui
    helix
    hexyl
    htop
    jq
    just
    lazydocker
    lazygit
    lnav
    lsd
    mdbook
    mosh
    mprocs
    navi
    neovim
    nethogs
    netscanner
    ninja
    procs
    ripgrep
    sheldon
    skim
    starship
    stow
    taskwarrior
    tealdeer
    television
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
