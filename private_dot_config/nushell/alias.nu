
alias fzfm = fzf --height 60% --reverse +s

###############################################################################
# cd & ls
###############################################################################

alias l = ezam
def --env cl [
  dir?: string  # Optional argument
] {
  let target_dir = if $dir != null {
    $dir
  } else {
    ls -a | where type in ['dir', 'symlink'] | sort-by modified -r | get name | to text | fzfm
  }

  if $target_dir != null {
    cd $target_dir
    l
  } else {
    print "No directory selected."
  }
}

def vc [query?: string] {
  let file = (
    ls -a
    | where type in ['file', 'symlink']
    | sort-by modified -r
    | get name
    | str join (char nl)
    | fzfm --query ($query | default "")
  )

  if $file != "" {
    nvim $file
  }
}

def --env cf [query?: string] {
    let selected = (fd --type f --type l --hidden --follow 
        | fzfm --query ($query | default "")
    )

    if $selected != null and ($selected | str trim) != "" {
        cd ($selected | path dirname)
    }
}

###############################################################################
# Just
###############################################################################

alias j = commandline edit (just.nu -f ./justfile -d . | str trim)
alias n = j
alias je = nvim ./justfile
alias ne = je
alias ni = commandline edit (just.nu -f ./.just/justfile -d . | str trim)
alias nie = nvim ./.just/justfile
alias na = commandline edit (just.nu -f ~/.config/my-scripts/justfile -d . | str trim)
alias nae = nvim ~/.config/my-scripts/justfile

def clip [] {
    if ($nu.os-info.name == "linux") {
        if (which wl-copy | is-empty) and (which xclip | is-empty) {
            print "Error: neither 'xclip' nor 'wl-copy' is installed"
        } else {
            $in | xclip -selection clipboard
        }
    } else if (open /proc/version | str contains "microsoft") {
        $in | clip.exe
    } else if ($nu.os-info.name == "windows") {
        $in | clip.exe
    } else if ($nu.os-info.name == "macos") {
        $in | pbcopy
    } else {
        print "Unsupported OS"
    }
}

alias x = commandline edit (~/.config/my-scripts/bin/autorun.sh | str trim)
alias xe = nvim ~/.config/my-scripts/bin/autorun.sh

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
alias chezd = cl ~/.local/share/chezmoi/
alias confd = cl ~/.config/
alias ghc = ~/.config/my-scripts/bin/gh-clone-fuzzy.sh
alias ghcu = ~/.config/my-scripts/bin/git-clone-user.sh
alias gfpa = git fetch --all --prune
alias h = cl ..
alias je = nvim ./justfile
alias lz = lazygit
alias nvimh = cl ~/.config/nvim/

def --env mc [dir: string] {
    mkdir $dir
    cl $dir
}

alias mycub = cl ~/my-cubrid/
alias v = nvim
alias prof = nvim ~/.local/share/chezmoi/private_dot_config/nushell/config.nu
alias w = which
alias wa = which -a
alias ze = zellij
alias zshrc = nvim ~/.local/share/chezmoi/dot_zshrc
