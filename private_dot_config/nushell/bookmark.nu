###############################################################################
# Directory Bookmarks (fzf TUI)
###############################################################################

const bookmark_file = ($nu.home-dir | path join ".bookmarks.nuon")

def _bm_load [] {
  if ($bookmark_file | path exists) {
    open $bookmark_file
  } else {
    []
  }
}

def _bm_save [] {
  $in | save --force $bookmark_file
}

def _bm_fmt [bookmarks: list] {
  let max_len = ($bookmarks | each { $in.name | str length } | math max)
  $bookmarks
  | each {|b| $"($b.name | fill -a l -w $max_len)  ($b.path)" }
  | str join (char nl)
}

def _bm_parse [line: string] {
  $line | str trim | split row -r '\s{2,}' | get 1
}

# Add current directory as a bookmark
def "bm add" [
  name?: string  # Optional display name (defaults to directory basename)
] {
  let dir = $env.PWD
  let label = if $name != null { $name } else { $dir | path basename }
  let bookmarks = (_bm_load)

  if ($bookmarks | where path == $dir | is-not-empty) {
    print $"Already bookmarked: ($dir)"
    return
  }

  $bookmarks | append {name: $label, path: $dir} | _bm_save
  print $"Bookmarked: ($label) -> ($dir)"
}

# Remove bookmark(s) via fzf picker
def "bm del" [] {
  let bookmarks = (_bm_load)
  if ($bookmarks | is-empty) {
    print "No bookmarks."
    return
  }

  let selected = (
    _bm_fmt $bookmarks
    | fzf --height 60% --reverse --multi --header "Select bookmark(s) to delete (TAB to multi-select)"
    | str trim
  )

  if $selected == "" { return }

  let paths_to_del = (
    $selected | lines | each {|line| _bm_parse $line }
  )

  let remaining = ($bookmarks | where { $in.path not-in $paths_to_del })
  $remaining | _bm_save
  print $"Deleted ($paths_to_del | length) bookmark\(s\)."
}

# List all bookmarks
def "bm list" [] {
  let bookmarks = (_bm_load)
  if ($bookmarks | is-empty) {
    print "No bookmarks."
    return
  }
  $bookmarks | table
}

def "bm a" [name?: string] { bm add $name }
def "bm d" [] { bm del }
def "bm l" [] { bm list }

# Pick a bookmark via fzf and cd to it
def --env bm [
  --add (-a)  # Add current directory as bookmark
  --del (-d)  # Delete bookmark(s) via fzf
] {
  if $add {
    bm add
    return
  }
  if $del {
    bm del
    return
  }

  let bookmarks = (_bm_load)
  if ($bookmarks | is-empty) {
    print "No bookmarks. Use 'bm add [name]' or 'bm -a' to add one."
    return
  }

  let selected = (
    _bm_fmt $bookmarks
    | fzf --height 60% --reverse --header "Bookmarks (Enter=cd, Ctrl-C=cancel)"
    | str trim
  )

  if $selected == "" { return }

  let dir = (_bm_parse $selected)

  if ($dir | path exists) {
    cl $dir
  } else {
    print $"Path no longer exists: ($dir)"
    print "Removing stale bookmark..."
    let remaining = ($bookmarks | where { $in.path != $dir })
    $remaining | _bm_save
  }
}
