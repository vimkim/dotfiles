def zellij-update-tabname-git [] {
  if ("ZELLIJ" in $env) {
    let current_dir = pwd;
    mut tab_name = if ($current_dir == $env.HOME) {
      "~"
    } else {
      ($current_dir | path parse | get stem | str substring 0..8)
    };

    # Single git call: lines are [is-inside-work-tree, superproject (maybe empty), toplevel]
    let git_info = try {
      git rev-parse --is-inside-work-tree --show-superproject-working-tree --show-toplevel err> /dev/null | lines
    } catch {
      []
    };

    if ($git_info | length) >= 2 {
      # First line is "true", remaining lines: if 3 lines then superproject + toplevel, if 2 lines then just toplevel
      let git_root = if ($git_info | length) >= 3 {
        $git_info | get 1
      } else {
        $git_info | get 1
      };

      let repo_name = ($git_root | path parse | get stem);
      let repo_name_len = ($repo_name | str length);

      let short_repo_name = if $repo_name_len > 9 {
        let repo_name_first = ($repo_name | str substring 0..4);
        let repo_name_last = ($repo_name | str substring ($repo_name_len - 4)..($repo_name_len - 1));
        $"($repo_name_first)*($repo_name_last)"
      } else {
        $repo_name
      };

      if (($git_root | str downcase) != ($current_dir | str downcase)) {
        let pwd_name = ($current_dir | path parse | get stem | str substring 0..1);
        $tab_name = $"($short_repo_name):($pwd_name)"
      } else {
        $tab_name = $short_repo_name
      }
    }

    # Look up tab ID by pane ID (focus-independent, race-free).
    let tab_id = try {
      let pane_id = $env.ZELLIJ_PANE_ID;
      zellij action list-panes --tab | lines | skip 1
        | where ($it | str contains $"terminal_($pane_id)")
        | first | split row -r "\\s\\s+" | get 0 | into int
    } catch {
      null
    };
    let tab_name = $tab_name;
    job spawn {
      if $tab_id != null {
        zellij action rename-tab --tab-id $tab_id $tab_name
      } else {
        zellij action rename-tab $tab_name
      }
    }
  }
}
