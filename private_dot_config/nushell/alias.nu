

def --env cl [
  dir?: string  # Optional argument
] {
  let target_dir = if $dir != null {
    $dir
  } else {
    ls -a | where type == 'dir' | get name | to text | fzf
  }

  if $target_dir != null {
    cd $target_dir
    ls
  } else {
    print "No directory selected."
  }
}

def vc [query?: string] {
  let file = (
    ls -a
    | where type == 'file'
    | get name
    | str join (char nl)
    | fzf --query ($query | default "")
  )

  if $file != "" {
    ^$env.EDITOR $file
  }
}

$env.config.hooks.env_change.PWD = $env.config.hooks.env_change.PWD | append {
  |before, after|
    let history_file = ($nu.home-path | path join ".local" "share" "nushell" "dir_history.txt")

    # Ensure the history file exists
    if not ($history_file | path exists) {
      mkdir ($history_file | path dirname)
      touch $history_file
    }

    # Read existing history
    let history = (open $history_file | lines)

    # Remove the new directory if it already exists to prevent duplicates
    let updated_history = ($history | filter { |dir| $dir != $after })

    # Prepend the new directory
    let updated_history = [$after] ++ $updated_history

    # Keep only the latest 30 entries
    let trimmed_history = ($updated_history | first 30)

    # Save back to the history file
    $trimmed_history | save -f --raw $history_file
}

def view-dir-history [] {
  let history_file = ($nu.home-path | path join ".local" "share" "nushell" "dir_history.txt")
  if ($history_file | path exists) {
    open $history_file | lines
  } else {
    print "No directory history found."
  }
}
alias vh = view-dir-history

def --env cd-dir-history [] {
  let history_file = ($nu.home-path | path join ".local" "share" "nushell" "dir_history.txt")
  if ($history_file | path exists) {
    let dir = (open $history_file | to text | fzf)
    if $dir != "" {
      cl $dir
    } else {
      print "No directory selected."
    }
  } else {
    print "No directory history found."
  }
}
alias ch = cd-dir-history

alias ali = nvim ~/.local/share/chezmoi/private_dot_config/nushell/alias.nu
alias c = cl
alias cz = zi
alias chez = chezmoi
alias chezd = cd ~/.local/share/chezmoi/
alias confd = cd ~/.config/
alias h = cl ..
alias j = just
alias je = nvim ./justfile
alias l = ls
alias lz = lazygit
alias v = nvim
alias prof = nvim ~/.local/share/chezmoi/private_dot_config/nushell/config.nu
alias w = which
alias wa = which -a
alias ze = zellij

