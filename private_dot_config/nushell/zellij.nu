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

      if (($git_root | str downcase) != ($current_dir | str downcase)) {
        let pwd_name = ($current_dir | path parse | get stem);
        $tab_name = $"($repo_name):($pwd_name)"
      } else {
        $tab_name = $repo_name
      }
    }

    # Vertical-tab sidebar (vtabs.kdl) is ~20 cols wide, so cap once here
    # instead of truncating each component. str substring clamps short names.
    let tab_name = ($tab_name | str substring 0..<20);

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
