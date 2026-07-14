def zellij-update-tabname-git [] {
  if ("ZELLIJ" in $env) {
    let current_dir = pwd;
    mut tab_name = if ($current_dir == $env.HOME) {
      "~"
    } else {
      ($current_dir | path parse | get stem)
    };

    # Single git call: lines are [is-inside-work-tree, superproject (maybe empty), toplevel]
    let git_info = try {
      git rev-parse --is-inside-work-tree --show-superproject-working-tree --show-toplevel err> /dev/null | lines
    } catch {
      []
    };

    if ($git_info | length) >= 2 {
      # First line is "true"; line index 1 is the git root we care about.
      let git_root = ($git_info | get 1);
      let repo_name = ($git_root | path parse | get stem);

      if (($git_root | str lowercase) != ($current_dir | str lowercase)) {
        let pwd_name = ($current_dir | path parse | get stem);
        $tab_name = $"($repo_name):($pwd_name)"
      } else {
        $tab_name = $repo_name
      }
    }

    # Vertical-tab sidebar (vtabs.kdl) is 32 cols wide (~27 for the name after
    # the marker + index prefix), so cap once here instead of truncating each
    # component. str substring clamps short names.
    let tab_name = ($tab_name | str substring 0..<27);

    # Look up tab ID by pane ID (focus-independent, race-free).
    let tab_id = try {
      let pane_id = $env.ZELLIJ_PANE_ID;
      zellij action list-panes --tab | lines | skip 1
        | where ($it | str contains $"terminal_($pane_id)")
        | first | split row -r "\\s\\s+" | get 0 | into int
    } catch {
      null
    };
    job spawn {
      if $tab_id != null {
        zellij action rename-tab --tab-id $tab_id $tab_name
      } else {
        zellij action rename-tab $tab_name
      }
    }
  }
}

# Spawn a NEW zellij session after fuzzy-picking a layout from
# ~/.config/zellij/layouts via fzf. Optional positional arg names the session;
# omit it to let zellij auto-generate the session name.
def zellij-new [name?: string] {
  let layout_dir = ($nu.home-dir | path join ".config" "zellij" "layouts")
  let layouts = (glob ($layout_dir | path join "*.kdl") | path parse | get stem | sort)

  if ($layouts | is-empty) {
    print $"No layouts found in ($layout_dir)"
    return
  }

  let chosen = (
    $layouts
    | str join (char nl)
    | fzf --height 60% --reverse --header "Select layout for new zellij session"
    | str trim
  )

  if ($chosen | is-empty) {
    print "No layout selected."
    return
  }

  if ($name | is-not-empty) {
    # -n/--new-session-with-layout, NOT --layout: combined with -s/--session,
    # --layout tries to add tabs to that (non-existent) session and aborts with
    # "There is no active session!". -n always starts a fresh session.
    zellij -s $name --new-session-with-layout $chosen
  } else {
    zellij --layout $chosen
  }
}

# zs / zn: start a new zellij session, fuzzily selecting a layout with fzf.
def zs [name?: string] { zellij-new $name }
def zn [name?: string] { zellij-new $name }
