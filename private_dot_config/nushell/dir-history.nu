# Shell adapter for the shared dir-history command and SQLite store.

def --env _dir_history_record [directory: string] {
  let previous_status = ($env.LAST_EXIT_CODE? | default 0)
  try {
    let result = (^dir-history record -- $directory | complete)
    if $result.exit_code != 0 { print -e ($result.stderr | str trim) }
  } catch {|error| print -e $error.msg }
  $env.LAST_EXIT_CODE = $previous_status
}

# Replace this module's previous hook, including the legacy JSON writer, on reload.
$env.config.hooks.env_change.PWD = (
  ($env.config.hooks.env_change.PWD? | default [])
  | where {|hook|
    let source = (try { view source $hook } catch { "" })
    $source !~ '_dir_history_(init|record)'
  }
  | append {|before after| _dir_history_record $after }
)

def view-dir-history [] {
  ^dir-history list --json | from json
}
alias vh = view-dir-history

def --env cd-dir-history [
  --forget (-f) # Remove selected paths from history only
  --delete (-d) # Confirm moving selected directories to trash
  --prune (-p)  # Remove missing directories from history
] {
  let mode_count = ([$forget $delete $prune] | where {|enabled| $enabled } | length)
  if $mode_count > 1 {
    error make {msg: "Use only one of --forget, --delete, or --prune."}
  }
  let options = if $forget { ["--forget"] } else if $delete { ["--delete"] } else if $prune { ["--prune"] } else { ["--json"] }
  if $forget or $delete or $prune {
    # Keep confirmation prompts connected to the terminal instead of capturing them.
    ^dir-history pick ...$options
    if $env.LAST_EXIT_CODE not-in [0 130] {
      error make {msg: $"Directory history command failed with status ($env.LAST_EXIT_CODE)."}
    }
    return
  }
  let result = (^dir-history pick ...$options | complete)
  if $result.exit_code == 130 { return }
  if $result.exit_code != 0 { error make {msg: ($result.stderr | str trim)} }
  if ($result.stderr | is-not-empty) { print -e ($result.stderr | str trim) }
  let selected = ($result.stdout | from json)
  if $selected != null { cl $selected }
}
alias ch = cd-dir-history
alias chf = cd-dir-history --forget
alias chd = cd-dir-history --delete
alias chp = cd-dir-history --prune
