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
    | prepend $after
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
