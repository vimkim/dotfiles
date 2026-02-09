alias fzfm = fzf --height 60% --reverse

###############################################################################
# cd & ls
###############################################################################

alias l = ezam
def --env cl [
  dir?: string # Optional argument
] {
  let target_dir = if $dir != null {
    $dir
  } else {
    # ls -a | where type in ['dir' 'symlink'] | sort-by modified -r | get name | to text | fzfm
    eza -l --no-permissions --no-user -a --icons=always --sort modified --reverse --color=always --only-dirs --show-symlinks
    | fzfm --ansi --query ""
    | str trim -l
    | split row -r '\s+'
    | get 5 -o
    | default null
  }

  if $target_dir == null {
    print "No directory selected."
    return
  }

  cd $target_dir

  let big_threshold = 400
  let entry_count   = (fd -d1 --hidden --no-ignore | wc -l | into int)
  let rows          = (term size | get rows)
  let max_lines     = ($rows * 0.8 | math floor)

  ezam
}

# def vc [query?: string] {
#   let file = (
#     ls -a
#     | where type in ['file' 'symlink']
#     | sort-by modified -r
#     | get name
#     | str join (char nl)
#     | fzfm --query ($query | default "")
#   )
#
#   if $file != "" {
#     nvim $file
#   }
# }
def vc [query?: string] {
  let file = (
    eza -a -l --no-permissions --no-user --icons=always --sort modified --reverse --color=always --only-files --show-symlinks
    | fzfm --ansi --query ($query | default "")
    | str trim -l
    | split row -r '\s+'
    | get 5 -o
    | default null
  )

  if $file == null {
    print "No file selected."
    return
  }

  nvim $file
}

def --env cf [query?: string] {
  let selected = (
    ^fd --type f --type l --no-ignore --hidden --follow
    | ^fzf --height 60% --reverse --query ($query | default "")
  )

  if $selected != null and ($selected | str trim) != "" {
    cd ($selected | path dirname)
  }
}

# Jump to the root directory of the current Git repository
def --env __git_root [] {
  let root = (git rev-parse --show-toplevel | str trim)
  if $root == "" {
    print $"Not inside a Git repository \(pwd: ($env.PWD)\)"
  } else {
    cd $root
  }
}

# Convenience alias: `gr` => go to git root
alias gr = __git_root
alias gcd = __git_root

###############################################################################
# clip
###############################################################################

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

###############################################################################
# Just
###############################################################################

alias n = commandline edit (just.nu -f ./justfile -d . | str trim)
alias j = just
alias je = nvim ./justfile
alias ne = je
alias ni = commandline edit (just.nu -f ./.just/justfile -d . | str trim)
alias nie = nvim ./.just/justfile
alias na = commandline edit (just.nu -f ~/.config/my-scripts/justfile -d . | str trim)
alias nae = nvim ~/.config/my-scripts/justfile
alias nae = do { nvim $"($env.HOME)/.local/share/chezmoi/private_dot_config/my-scripts/justfile" }

alias x = commandline edit (~/.config/my-scripts/bin/autorun.sh | str trim)
# alias xe = nvim ~/.config/my-scripts/bin/autorun.sh
def xe [] {
    let projtype = (detect-project.sh)
    nvim $"($env.HOME)/.local/share/chezmoi/private_dot_config/my-scripts/($projtype).just"
}

# alias n1 = commandline edit $"(just --dry-run -f ./justfile -d . n1 o+e>| str trim)"
# alias n2 = commandline edit $"(just --dry-run -f ./justfile -d . n2 o+e>| str trim)"
# alias n3 = commandline edit $"(just --dry-run -f ./justfile -d . n3 o+e>| str trim)"
# alias n4 = commandline edit $"(just --dry-run -f ./justfile -d . n4 o+e>| str trim)"
# alias n5 = commandline edit $"(just --dry-run -f ./justfile -d . n5 o+e>| str trim)"
# alias n6 = commandline edit $"(just --dry-run -f ./justfile -d . n6 o+e>| str trim)"
# alias n7 = commandline edit $"(just --dry-run -f ./justfile -d . n7 o+e>| str trim)"
# alias n8 = commandline edit $"(just --dry-run -f ./justfile -d . n8 o+e>| str trim)"
# alias n9 = commandline edit $"(just --dry-run -f ./justfile -d . n9 o+e>| str trim)"

alias n1 = just n1
alias n2 = just n2
alias n3 = just n3
alias n4 = just n4
alias n5 = just n5
alias n6 = just n6
alias n7 = just n7
alias n8 = just n8
alias n9 = just n9

alias nb = just nb
alias nbr = just build-run
alias nc = just nc
alias nd = just nd
alias ns = just ns
alias np = just np
alias nt = just nt
alias nl = just nl

###############################################################################
# Directory History
###############################################################################

let history_file = ($env.HOME | path join ".local" "share" "nu" "dirlog.json")

$env.config.hooks.env_change.PWD = (
  $env.config.hooks.env_change.PWD | append {|before after|
    # ensure directory & file exist
    if not ($history_file | path exists) {
      mkdir ($history_file | path dirname)
      [] | save --force $history_file
    }
    open $history_file
    | collect # gather into a list
    | prepend $after # new $after at index 0
    | uniq # de‐duplicate (keeps first occurrence)
    | take 60 # keep most recent 60
    | save --force $history_file
  }
)

def view-dir-history [] {
  if ($history_file | path exists) {
    open $history_file
  } else {
    print "No directory history found."
  }
}
alias vh = view-dir-history

def --env cd-dir-history [] {
  if not ($history_file | path exists) {
    print "No directory history found."
    return
  }

  # let dir = (open $history_file | to text | fzfm)
  let dir = ( open $history_file | to text | each {|l| $"(ansi blue)($l)(ansi reset)" } | fzfm --ansi )

  if $dir == "" {
    print "No directory selected."
    return
  }

  if ($dir | path exists) {
    cl $dir
  } else {
    # Remove the missing path from the history file
    open $history_file
    | collect
    | where { $in != $dir }
    | save --force $history_file

    print $"Removed missing path from history: ($dir)"
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

$env.config.keybindings = (
  $env.config.keybindings | append {
    name: yazi_ctrl_y
    modifier: control
    keycode: char_y
    mode: emacs
    event: {
      send: executehostcommand
      cmd: "y"
    }
  }
)

###############################################################################
# Misc Aliases in Alphabetical Order
###############################################################################

alias ali = nvim ~/.local/share/chezmoi/private_dot_config/nushell/alias.nu
alias battery = do { upower -e | fzf --preview='upower -i {}' }
alias c = cl
alias crc = crc.sh
alias cx = cl (fd -H -I -t d | fzfm)
alias cz = zi
alias activate = overlay use .venv/bin/activate.nu
def dea [] { deactivate }
alias chez = chezmoi
alias chezd = cl ~/.local/share/chezmoi/
alias caps = gsettings set org.gnome.desktop.input-sources xkb-options "['ctrl:nocaps']"
alias caps_reset = gsettings reset org.gnome.desktop.input-sources xkb-options
alias conf = cl ~/.config/
alias confd = cl ~/.config/
alias e = ~/.config/my-scripts/bin/cargo-run-example.sh
alias fda = fd -H -I
alias ff = fastfetch
alias fmake = fzf-make
alias fm = fzf-make
alias ghc = ~/.config/my-scripts/bin/github-clone-confirm.sh
alias ghcf = ~/.config/my-scripts/bin/gh-clone-fuzzy.sh
alias ghcu = ~/.config/my-scripts/bin/git-clone-user.sh
alias gfpa = git fetch --all --prune
alias gl = ~/.config/my-scripts/bin/git-log.sh
alias gld = do { ~/.config/my-scripts/bin/git-log.sh develop }
alias glh = do { ~/.config/my-scripts/bin/git-log.sh HEAD }
alias glf = ~/.config/my-scripts/bin/git-log-find.sh
alias gloga = with-env {GL_OPS: "--all"} { git-log.sh }
alias gst = git status
alias gsw = git switch
alias h = cl ..

# alias he = bat -p -l help
def he [cmd?: string] {
    if ($cmd | is-empty) {
        # no argument: act as a pipe filter
        bat -p -l help
    } else {
        let help_output = (do { ^$cmd --help } | complete | get stdout | str trim)
        if ($help_output | is-empty) {
            print $"No help available for: ($cmd)"
        } else {
            $help_output | bat -p -l help
        }
    }
}

alias hg = hgrep
alias i = cl
alias ii = xdg-open
alias je = nvim ./justfile

def lf [...file: string] {
    let cols = (tput cols)
    eza ...($file | default []) -a -l --icons=always --color=always --sort=modified --only-files --show-symlinks --width=($cols) | less -rXFS
}

alias lj = lazyjj
alias lz = lazygit
alias lzd = lazydocker
alias lzpu = with-env {DOCKER_HOST: "unix:///run/user/1000/podman/podman.sock"} { lazydocker }
alias lzps = with-env {DOCKER_HOST: "unix:///run/podman/podman.sock"} { sudo /home/vimkim/.nix-profile/bin/lazydocker }
alias lzp = lzps

def --env mc [dir: string] {
  mkdir $dir
  cl $dir
}

alias mycub = cl ~/my-cubrid/
alias my-cargo-install = ~/.config/my-scripts/bin/my-cargo-install.nu
alias nvimh = cl ~/.config/nvim/
alias rgall = rg --hidden --no-ignore
alias rgf = rgf.sh
alias sl = l
alias starbucks_archlinux = curl -v http://gstatic.com/generate_204
alias sctl = systemctl
alias perf-enable = sudo sysctl kernel.perf_event_paranoid=-1
alias pf = ~/.config/my-scripts/bin/ps-fuzzy.sh
alias ports = somo
alias ports-tcp = somo -t
alias ppath = echo $env.PATH
alias prof = nvim ~/.local/share/chezmoi/private_dot_config/nushell/config.nu
alias re = ~/.config/my-scripts/bin/rerun-on-enter.nu
alias t = just default
alias ts = tspin
# alias todo = nvim ~/.todo.md # replaced with vimkim/todo
alias v = nvim
alias w = which
alias wa = which -a
alias za = do { SHELL=nu attach-or-new.sh }
alias ze = zellij
alias zs = zellij -s
alias zshrc = nvim ~/.local/share/chezmoi/dot_zshrc
