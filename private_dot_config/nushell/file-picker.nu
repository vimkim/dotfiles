def __pick_file_path [query?: string] {
  let selected = (^file-picker.sh -- ($query | default "") | str trim)

  if $selected != "" {
    $selected
  }
}

def __pick_current_file_path [query?: string] {
  let selected = (^file-picker.sh --max-depth 1 -- ($query | default "") | str trim)

  if $selected != "" {
    $selected
  }
}

def fp [query?: string] {
  __pick_file_path ($query | default "")
}

def fc [query?: string] {
  let selected = (__pick_file_path ($query | default ""))

  if $selected != null and ($selected | str trim) != "" {
    $selected | clip
  }
}

def --env cf [query?: string] {
  let selected = (__pick_file_path ($query | default ""))

  if $selected != null and ($selected | str trim) != "" {
    cd ($selected | path dirname)
  }
}

def vc [query?: string] {
  let selected = (__pick_current_file_path ($query | default ""))

  if $selected != null and ($selected | str trim) != "" {
    ^$env.EDITOR $selected
  }
}
