# config.nu
#
# Installed by:
# version = "0.104.0"
#
# This file is used to override default Nushell settings, define
# (or import) custom commands, or run any other startup tasks.
# See https://www.nushell.sh/book/configuration.html
#
# This file is loaded after env.nu and before login.nu
#
# You can open this file in your default editor using:
# config nu
#
# See `help config nu` for more options
#
# You can remove these comments if you want or leave
# them for future reference.

# source ~/.config/nushell/zshrc.nu
# source ~/.config/nushell/zalias.nu

use std "path add"
path add /nix/var/nix/profiles/default/bin/
path add ~/.nix-profile/bin/
path add /home/linuxbrew/.linuxbrew/bin
path add ~/.config/my-scripts/bin/
path add ~/my-cubrid/bin/
path add ~/mybin/
path add ~/.local/bin/
path add /opt/bison-3.0.5/bin/

if (sys host | get name | str downcase | str contains 'fedora') and ('/usr/lib64/ccache' | path exists) {
    path add /usr/lib64/ccache
    $env.LANG = 'en_US.utf8'
}

if (sys host | get name | str downcase | str contains 'rocky') and ('/usr/lib64/ccache' | path exists) {
    # path add /usr/lib64/ccache
    $env.LANG = 'en_US.utf8'
}

if (sys host | get name | str downcase | str contains 'arch') and ('/usr/lib/ccache/bin' | path exists) {
    # path add /usr/lib/ccache/bin
}

if (sys host | get name | str downcase | str contains 'rocky') and (sys host | get os_version | str contains '8' ) {
    $env.NIX_SSL_CERT_FILE = '/etc/ssl/certs/ca-bundle.crt'
}

source ~/.local/share/atuin/init.nu
source ~/.zoxide.nu
use ($nu.default-config-dir | path join mise.nu)
source ($nu.default-config-dir | path join eza.nu)

let os_name = (sys host | get name)
if $os_name == "Arch Linux" {
    source ~/.config/nushell/archlinux.nu
}

source ~/.config/nushell/alias.nu
source ~/my-cubrid/aliases.nu
source ~/.config/nushell/completions.nu
source ~/.config/nushell/zellij.nu

# wezterm fix: https://github.com/nushell/nushell/issues/5585
# no need for wezterm nightly build after 2025
$env.config.shell_integration.osc133 = false

$env.config.show_banner = false

# fzf-tab like completion
$env.config.completions = {
  case_sensitive: false
  algorithm: "fuzzy"
  external: {
    enable: true
  }
}

$env.config = {
  hooks: {
    pre_prompt: [{ ||
      if (which direnv | is-empty) {
        return
      }

      direnv export json | from json | default {} | load-env
      if 'ENV_CONVERSIONS' in $env and 'PATH' in $env.ENV_CONVERSIONS {
        $env.PATH = do $env.ENV_CONVERSIONS.PATH.from_string $env.PATH
      }
    }],
  }
}

$env.config.hooks.env_change.PWD = (
    $env.config.hooks.env_change.PWD | append {|before, after|
        zellij-update-tabname-git 
    }
)

$env.EDITOR = 'nvim'
$env.config.buffer_editor = 'nvim-nu.sh' # at ~/.config/my-scripts/bin
export-env { $env.MAKEFLAGS = $"-j(nproc)"}

if (which sccache | is-not-empty ) {
    export-env {
        $env.RUSTC_WRAPPER = 'sccache'
        # $env.CC = 'sccache cc'
        # $env.CXX = 'sccache cpp'
    }
}

###############################################################################
# Vcpkg
###############################################################################

if ($"($env.HOME)/vcpkg" | path exists) {
    $env.VCPKG_ROOT = $"($env.HOME)/vcpkg"
    path add $env.VCPKG_ROOT
}

###############################################################################
# Zellij
###############################################################################

# https://www.grailbox.com/2023/07/autostart-zellij-in-nushell/
# $env.ZELLIJ_AUTO_ATTACH = 'true'

def start_zellij [] {
  if 'ZELLIJ' not-in ($env | columns) {
    if 'ZELLIJ_AUTO_ATTACH' in ($env | columns) and $env.ZELLIJ_AUTO_ATTACH == 'true' {
      ~/.config/my-scripts/bin/attach-or-new.sh
    } else {
      zellij
    }

    if 'ZELLIJ_AUTO_EXIT' in ($env | columns) and $env.ZELLIJ_AUTO_EXIT == 'true' {
      exit
    }
  }
}

# start_zellij

###############################################################################
# Starship
###############################################################################
mkdir ($nu.data-dir | path join "vendor/autoload")
starship init nu | save -f ($nu.data-dir | path join "vendor/autoload/starship.nu")

zellij ls

