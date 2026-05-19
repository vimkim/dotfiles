# source ~/nu_scripts/custom-completions/git/git-completions.nu
# source ~/nu_scripts/custom-completions/cargo/cargo-completions.nu
# source ~/nu_scripts/custom-completions/docker/docker-completions.nu
# source ~/nu_scripts/custom-completions/gh/gh-completions.nu
# source ~/nu_scripts/custom-completions/just/just-completions.nu
# source ~/nu_scripts/custom-completions/make/make-completions.nu
# source ~/nu_scripts/custom-completions/rg/rg-completions.nu
# source ~/nu_scripts/custom-completions/ssh/ssh-completions.nu
# source ~/nu_scripts/custom-completions/tcpdump/tcpdump-completions.nu
# source ~/nu_scripts/custom-completions/tealdeer/tldr-completions.nu
# source ~/nu_scripts/custom-completions/uv/uv-completions.nu

# carapace as external completer — covers ~1000 CLIs incl. git branches.
# Must be a let-bound name, not an inline closure literal — nushell drops
# inline closures stored in $env.config across the config-load boundary.
let carapace_completer = {|spans: list<string>|
  carapace $spans.0 nushell ...$spans | from json
}
$env.config.completions = {
  case_sensitive: false
  algorithm: "fuzzy"
  external: {
    enable: true
    completer: $carapace_completer
  }
}
