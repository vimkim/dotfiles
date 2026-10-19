# Set the EZA_COLORS environment variable
$env.EZA_COLORS = $"da=35;"

# Define common options as a list (local variable)
let eza_common_options = [
  --group-directories-first
  -aF
  --time-style=relative
]

# Define long options by appending to the common options
$env.EZA_LONG_OPTIONS = (
  $eza_common_options ++ [
    --long
    --git
    --color=always
  ]
)

# Define sort options
$env.EZA_SORT_MODIFIED = [
  --sort=modified
]

# Shared with Bash and Zsh: newest entries first, capped to one terminal screen.
def --wrapped ezam [...args: string] {
  ^ls-one-page ...$args
}

# Define the 'l' alias/function
def ezaml [...args] {
  eza --group-directories-first -alF --time-style=relative --icons --sort=modified ...$args
}
alias ll = ezaml
