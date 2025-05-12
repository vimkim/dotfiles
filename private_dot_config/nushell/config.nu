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
path add "/home/linuxbrew/.linuxbrew/bin"
path add ~/.config/my-scripts/bin/
path add ~/my-cubrid/bin/

source ~/.local/share/atuin/init.nu
source ~/.zoxide.nu
use ($nu.default-config-dir | path join mise.nu)
source ($nu.default-config-dir | path join eza.nu)

source ~/.config/nushell/alias.nu

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
    }]
  }
}

###############################################################################
# Starship
###############################################################################
mkdir ($nu.data-dir | path join "vendor/autoload")
starship init nu | save -f ($nu.data-dir | path join "vendor/autoload/starship.nu")

use ($nu.default-config-dir | path join mise.nu)
