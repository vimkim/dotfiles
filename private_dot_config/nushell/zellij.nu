def zellij-update-tabname-git [] {
  if ("ZELLIJ" in $env) {
    let current_dir = pwd;
    mut tab_name = if ($current_dir == $env.HOME) {
      "~"
    } else {
      let current_dir_len = ($current_dir | str length);
      ($current_dir | path parse | get stem | str substring 0..8)
    };

    let in_git = (try { git rev-parse --is-inside-work-tree err> /dev/null } catch { "false" });
    if ($in_git | into bool) {
      # Get the git superproject root if available.
      let git_root_super = (try { git rev-parse --show-superproject-working-tree } catch { "" });
      let git_root = if ($git_root_super == "") {
        (try { git rev-parse --show-toplevel } catch { "" })
      } else {
        $git_root_super
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

    # Update the zellij tab name.
    zellij action rename-tab $tab_name;
  }
}
