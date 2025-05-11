

def --env cl [
  dir?: string  # Optional argument
] {
  let target_dir = if $dir != null {
    $dir
  } else {
    ls | where type == 'dir' | get name | to text | fzf
  }

  if $target_dir != null {
    cd $target_dir
    ls
  } else {
    print "No directory selected."
  }
}

def vc [] {
  let file = (ls | where type == 'file' | get name | str join (char nl) | fzf)
  if $file != "" {
    ^$env.EDITOR $file
  }
}

alias c = cl
alias cz = zi
alias chez = chezmoi
alias chezd = cd ~/.local/share/chezmoi/
alias confd = cd ~/.config/
alias l = ls
alias lz = lazygit
alias v = nvim

