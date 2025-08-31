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
    ls -a | where type in ['dir' 'symlink'] | sort-by modified -r | get name | to text | fzfm
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
    | where type in ['file' 'symlink']
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
  let selected = (
    fd --type f --type l --no-ignore --hidden --follow
    | fzfm --query ($query | default "")
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

  let dir = (open $history_file | to text | fzfm)
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
alias c = cl
alias cx = cl (fd -H -I -t d | fzfm)
alias cz = zi
alias activate = overlay use .venv/bin/activate.nu
alias dea = deactivate
alias chez = chezmoi
alias chezd = cl ~/.local/share/chezmoi/
alias caps = gsettings set org.gnome.desktop.input-sources xkb-options "['ctrl:nocaps']"
alias caps_reset = gsettings reset org.gnome.desktop.input-sources xkb-options
alias conf = cl ~/.config/
alias confd = cl ~/.config/
alias fda = fd -H -I
alias ff = fastfetch
alias ghc = ~/.config/my-scripts/bin/github-clone-confirm.sh
alias ghcf = ~/.config/my-scripts/bin/gh-clone-fuzzy.sh
alias ghcu = ~/.config/my-scripts/bin/git-clone-user.sh
alias gfpa = git fetch --all --prune
alias gl = ~/.config/my-scripts/bin/git-log.sh
alias glf = ~/.config/my-scripts/bin/git-log-find.sh
alias gloga = with-env {GL_OPS: "--all"} { git-log.sh }
alias gst = git status
alias gsw = git switch
alias h = cl ..
alias i = cl
alias ii = xdg-open
alias je = nvim ./justfile
alias lz = lazygit
alias lzd = lazydocker
alias lzpu = with-env {DOCKER_HOST: "unix:///run/user/1000/podman/podman.sock"} { lazydocker }
alias lzps = with-env {DOCKER_HOST: "unix:///run/podman/podman.sock"} { sudo /home/vimkim/.nix-profile/bin/lazydocker }
alias lzp = lzps
alias nvimh = cl ~/.config/nvim/

def --env mc [dir: string] {
  mkdir $dir
  cl $dir
}

alias mycub = cl ~/my-cubrid/
alias rga = rg --hidden --no-ignore
alias sl = l
alias sctl = systemctl
alias perf-enable = sudo sysctl kernel.perf_event_paranoid=-1
alias pf = ~/.config/my-scripts/bin/ps-fuzzy.sh
alias ports = somo
alias ports-tcp = somo -t
alias prof = nvim ~/.local/share/chezmoi/private_dot_config/nushell/config.nu
alias t = tspin
alias todo = nvim ~/.todo.md
alias v = nvim
alias w = which
alias wa = which -a
alias za = attach-or-new.sh
alias ze = zellij
alias zs = zellij -s
alias zshrc = nvim ~/.local/share/chezmoi/dot_zshrc
