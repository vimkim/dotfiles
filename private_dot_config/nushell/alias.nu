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

  ^$env.EDITOR $file
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

# Custom completer for just recipes
def "nu-complete just-recipes" [] {
    if (not ("./justfile" | path exists)) { return [] }
    just -f ./justfile -d . --summary | split row ' ' | where { $in != "" }
}

# n: no args → fzf + paste to edit line; with args → execute just directly
def --env --wrapped n [...args: string@"nu-complete just-recipes"] {
    if ($args | is-empty) {
        commandline edit (just.nu -f ./justfile -d . | str trim)
    } else {
        just -f ./justfile -d . ...$args
    }
}
alias j = just

# jj/nn/jc: fzf-pick a recipe, then paste `just <recipe>` onto the prompt
# (instead of running it inside `just --choose`). Pressing Enter runs it AND
# lets the atuin pre_execution hook record `just <recipe>`, so Ctrl-R can
# recall the exact recipe later. Editable too — add args before Enter.
def --env jj [] {
    let recipe = (just-pick.nu -f ./justfile -d . | str trim)
    if ($recipe | is-not-empty) {
        commandline edit $"just ($recipe)"
    }
}
alias nn = jj
alias jc = jj
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

def _dir_history_init [] {
  if not ($history_file | path exists) {
    mkdir ($history_file | path dirname)
    [] | save --force $history_file
  }
}

def _dir_history_load [] {
  if not ($history_file | path exists) {
    return []
  }

  try {
    open $history_file
    | default []
    | where {|dir| (($dir | describe) == "string") and (($dir | str trim) != "") }
  } catch {
    []
  }
}

def _dir_history_save [] {
  mkdir ($history_file | path dirname)
  $in
  | collect
  | uniq
  | take 60
  | save --force $history_file
}

def _dir_history_forget [paths: list<string>] {
  if ($paths | is-empty) {
    return
  }

  let doomed = ($paths | uniq)
  _dir_history_load
  | where {|dir| $dir not-in $doomed }
  | _dir_history_save
}

def _dir_history_pick [
  --multi (-m)
  --header: string = "Directory history (Enter=cd, Ctrl-C=cancel)"
] {
  let dirs = (_dir_history_load)
  if ($dirs | is-empty) {
    return []
  }

  mut args = ["--height" "60%" "--reverse" "--ansi" "--header" $header]
  if $multi {
    $args = ($args | append "--multi")
  }

  let result = (
    $dirs
    | each {|l| $"(ansi blue)($l)(ansi reset)" }
    | str join (char nl)
    | ^fzf ...$args
    | complete
  )

  if $result.exit_code != 0 {
    return []
  }

  $result.stdout
  | str trim
  | lines
  | each {|line| $line | ansi strip | str trim }
  | where {|line| $line != "" }
}

def _dir_history_prune [] {
  let before = (_dir_history_load)
  let kept = ($before | where {|dir| $dir | path exists })
  $kept | _dir_history_save

  print $"Pruned (($before | length) - ($kept | length)) stale path\(s\)."
}

def _dir_history_delete [dirs: list<string>] {
  if ($dirs | is-empty) {
    return
  }

  print "Selected for trash:"
  $dirs | each {|dir| print $"  ($dir)" }

  let answer = (
    input --numchar 1 $"Trash ($dirs | length) selected path\(s\)? [y/N] "
    | str downcase
    | str trim
  )
  print ""

  if $answer != "y" {
    print "Delete cancelled."
    return
  }

  let cwd = ($env.PWD | path expand)
  let home = ($env.HOME | path expand)
  mut trashed = []
  mut forgotten = []
  mut skipped = []

  for dir in $dirs {
    if not ($dir | path exists) {
      print $"Removing stale history entry: ($dir)"
      $forgotten = ($forgotten | append $dir)
      continue
    }

    let full = ($dir | path expand)
    if ($full == "/") or ($full == $home) or ($cwd == $full) or ($cwd | str starts-with $"($full)/") {
      print $"Skipping protected/current path: ($dir)"
      $skipped = ($skipped | append $dir)
      continue
    }

    let trash_result = (try {
      rm --trash --recursive $dir
      {ok: true, msg: ""}
    } catch {|err|
      {ok: false, msg: $err.msg}
    })

    if $trash_result.ok {
      $trashed = ($trashed | append $dir)
    } else {
      print $"Failed to trash: ($dir)"
      print $trash_result.msg
      $skipped = ($skipped | append $dir)
    }
  }

  let remove_from_history = ($trashed | append $forgotten)
  if ($remove_from_history | is-not-empty) {
    _dir_history_forget $remove_from_history
  }

  print $"Trashed ($trashed | length) dir\(s\); removed ($forgotten | length) stale entr\(y/ies\); skipped ($skipped | length)."
}

$env.config.hooks.env_change.PWD = (
  ($env.config.hooks.env_change.PWD? | default []) | append {|before after|
    _dir_history_init
    _dir_history_load
    | prepend $after # new $after at index 0
    | _dir_history_save
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

def --env cd-dir-history [
  --forget (-f) # Remove selected path(s) from history only
  --delete (-d) # Move selected dir(s) to trash and remove them from history
  --prune (-p)  # Remove all missing path(s) from history
] {
  _dir_history_init

  let mode_count = ([$forget $delete $prune] | where {|enabled| $enabled } | length)
  if $mode_count > 1 {
    print "Use only one of --forget, --delete, or --prune."
    return
  }

  if $prune {
    _dir_history_prune
    return
  }

  if ((_dir_history_load) | is-empty) {
    print "No directory history found."
    return
  }

  if $forget {
    let dirs = (_dir_history_pick --multi --header "Directory history (TAB=multi, Enter=forget selected)")
    if ($dirs | is-empty) {
      print "No directory selected."
      return
    }

    _dir_history_forget $dirs
    print $"Removed ($dirs | length) path\(s\) from history."
    return
  }

  if $delete {
    let dirs = (_dir_history_pick --multi --header "Directory history (TAB=multi, Enter=trash selected dir(s))")
    if ($dirs | is-empty) {
      print "No directory selected."
      return
    }

    _dir_history_delete $dirs
    return
  }

  let selected = (_dir_history_pick)

  if ($selected | is-empty) {
    print "No directory selected."
    return
  }

  let dir = ($selected | first)

  if ($dir | path exists) {
    cl $dir
  } else {
    _dir_history_forget [$dir]
    print $"Removed missing path from history: ($dir)"
  }
}
alias ch = cd-dir-history
alias chf = cd-dir-history --forget
alias chd = cd-dir-history --delete
alias chp = cd-dir-history --prune

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
alias ai = claude --dangerously-skip-permissions
alias battery = do { upower -e | fzf --preview='upower -i {}' }
alias c = cl
alias cla = claude
alias cc = claude
alias cyo = claude --dangerously-skip-permissions
alias cds = claude --dangerously-skip-permissions
alias crc = crc.sh
alias cx = cl (fd -H -I -t d | fzfm)
alias cz = zi
alias activate = overlay use .venv/bin/activate.nu
def dea [] { deactivate }
alias chez = chezmoi
alias chezd = cl ~/.local/share/chezmoi/
def chzdiff [] { chezmoi diff | diffnav }
def chezdiff [] { chzdiff }
# dv: fzf-pick two revisions, then drop the nvim Diffview command on the prompt to edit/run.
# --wrapped forwards extra flags/args to git-diffview, e.g. `dv -r` (incl. remote branches), `dv -3`, `dv master`.
def --wrapped dv [...rest] { commandline edit (git diffview -p ...$rest | str trim) }
# dn: fzf-pick two refs from the commit graph, then drop the `git diff A B | diffnav` command on the prompt to edit/run.
# --wrapped forwards extra args to git-diffnav, e.g. `dn HEAD~1` (pre-fill the base ref).
def --wrapped dn [...rest] { commandline edit (git diffnav -p ...$rest | str trim) }
alias caps = gsettings set org.gnome.desktop.input-sources xkb-options "['ctrl:nocaps']"
alias caps_reset = gsettings reset org.gnome.desktop.input-sources xkb-options
alias conf = cl ~/.config/
alias confd = cl ~/.config/
alias e = ~/.config/my-scripts/bin/cargo-run-example.sh
alias fda = fd -H -I
alias ff = fastfetch
alias fmake = fzf-make
alias fm = fzf-make
alias gh_auth_login = with-env { BROWSER: "echo" } { gh auth login }
alias ghc = ~/.config/my-scripts/bin/github-clone-confirm.sh
alias ghcf = ~/.config/my-scripts/bin/gh-clone-fuzzy.sh
alias ghcu = ~/.config/my-scripts/bin/git-clone-user.sh

# My open PRs across every repo (focus state at a glance)
alias ghmy = gh search prs --author=@me --state=open

# PR dashboard: open PRs grouped by review state — the "what needs my attention" view.
# Uses GraphQL because `gh search prs` doesn't expose reviewDecision; viewer.pullRequests does.
def ghpd [] {
  let query = "{ viewer { pullRequests(first: 50, states: OPEN, orderBy: {field: UPDATED_AT, direction: DESC}) { nodes { number title isDraft reviewDecision repository { nameWithOwner } updatedAt } } } }"
  gh api graphql -f $"query=($query)"
  | from json
  | get data.viewer.pullRequests.nodes
  | each {|p|
      let state = (if $p.isDraft { "DRAFT" } else if ($p.reviewDecision | is-empty) { "PENDING" } else { $p.reviewDecision })
      # Focus order: things you can act on now sort first
      let priority = (match $state {
        "CHANGES_REQUESTED" => 0
        "APPROVED" => 1
        "PENDING" => 2
        "REVIEW_REQUIRED" => 3
        "DRAFT" => 4
        _ => 5
      })
      {
        repo: $p.repository.nameWithOwner
        pr: $"#($p.number)"
        state: $state
        priority: $priority
        updated: ($p.updatedAt | into datetime | format date "%Y-%m-%d")
        title: $p.title
      }
    }
  | sort-by priority updated
  | reject priority
}

# PRs where someone is waiting on you to review
alias ghrr = gh search prs --review-requested=@me --state=open

alias ghpr = do { gh pr view --json url -q .url }
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
alias ta = tmux a
def tsn [name: string] { tmux new -d -s $name }
alias ts = tspin
# alias todo = nvim ~/.todo.md # replaced with vimkim/todo
alias v = nvim
alias w = which
alias wa = which -a
source ~/.config/nushell/bookmark.nu
alias ba = bm add
alias bd = bm del
alias bl = bm list

alias za = do { SHELL=nu zellij-attach-or-new.sh }
alias zv = do { SHELL=nu zellij-attach-or-new.sh vtabs }
alias ze = zellij
# zs / zn are defined in zellij.nu (fzf layout picker -> new session)
alias zshrc = nvim ~/.local/share/chezmoi/dot_zshrc
