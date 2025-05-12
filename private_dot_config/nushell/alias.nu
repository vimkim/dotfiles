
alias fzfm = fzf --height 60% --reverse +s

def --env cl [
  dir?: string  # Optional argument
] {
  let target_dir = if $dir != null {
    $dir
  } else {
    ls -a | where type == 'dir' | sort-by modified -r | get name | to text | fzfm
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
    | sort-by modified -r
    | get name
    | str join (char nl)
    | fzfm --query ($query | default "")
  )

  if $file != "" {
    nvim $file
  }
}
###############################################################################
# Just
###############################################################################

alias j = commandline edit (just.nu -f ./justfile -d .)
alias n = j
alias je = nvim ./justfile
alias ne = je
alias ni = nvim ./.local/just

###############################################################################
# Directory History
###############################################################################

let history_file = ($nu.home-path | path join ".local" "share" "nu" "dirlog.json")

$env.config.hooks.env_change.PWD = (
    $env.config.hooks.env_change.PWD | append {|before, after|
        # ensure directory & file exist
        if not ($history_file | path exists) {
            mkdir ($history_file | path dirname)
            [] | save --force $history_file
        }
        open $history_file
        | collect              # gather into a list
        | prepend $after       # new $after at index 0
        | uniq                 # de‐duplicate (keeps first occurrence)
        | take 30              # keep most recent 30
        | save --force $history_file
    }
)

def view-dir-history [] {
  if ($history_file | path exists) {
    open $history_file | lines
  } else {
    print "No directory history found."
  }
}
alias vh = view-dir-history

def --env cd-dir-history [] {
  if ($history_file | path exists) {
    let dir = (open $history_file | to text | fzfm)
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

###############################################################################
# Yazi
###############################################################################
def --env y [...args] {
	let tmp = (mktemp -t "yazi-cwd.XXXXXX")
	yazi ...$args --cwd-file $tmp
	let cwd = (open $tmp)
	if $cwd != "" and $cwd != $env.PWD {
		cd $cwd
	}
	rm -fp $tmp
}

###############################################################################
# Misc Aliases in Alphabetical Order
###############################################################################

alias ali = nvim ~/.local/share/chezmoi/private_dot_config/nushell/alias.nu
alias c = cl
alias cx = cl (fd -H -I -t d | fzfm)
alias cz = zi
alias chez = chezmoi
alias chezd = cd ~/.local/share/chezmoi/
alias confd = cd ~/.config/
alias h = cl ..
alias je = nvim ./justfile
alias l = ezam
alias lz = lazygit
alias nvimh = cl ~/.config/nvim/
alias mycub = cl ~/my-cubrid/
alias v = nvim
alias prof = nvim ~/.local/share/chezmoi/private_dot_config/nushell/config.nu
alias w = which
alias wa = which -a
alias ze = zellij

