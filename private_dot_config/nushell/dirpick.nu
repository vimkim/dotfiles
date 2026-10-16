# Managed by chezmoi. Based on Dirpick's --print-nu-wrapper (v0.1).
# config.nu imports dp for directory changes through Ctrl-G.
export def --env dp [] {
    let result = (do { ^dirpick --json } | complete)
    if $result.exit_code != 0 {
        error make {msg: $"Dirpick failed: ($result.stderr)"}
    }
    if ($result.stdout | str trim | is-empty) { return }
    let action = ($result.stdout | from json --strict)
    if not (($action | describe) | str starts-with 'record<') {
        error make {msg: 'Invalid Dirpick action: expected one record'}
    }
    if ($action | columns | sort) != ['action', 'path'] {
        error make {msg: 'Invalid Dirpick action: expected only action and path'}
    }
    if ($action.action | describe) != 'string' or $action.action != 'cd' {
        error make {msg: 'Invalid Dirpick action: expected cd'}
    }
    if ($action.path | describe) != 'string' {
        error make {msg: 'Invalid Dirpick action: expected a string path'}
    }
    if not ($action.path | str starts-with '/') {
        error make {msg: 'Invalid Dirpick action: expected an absolute path'}
    }
    # The final separator preserves trailing whitespace/newlines through Nu cd.
    let destination = $"($action.path)/"
    if ($destination | path type) != 'dir' {
        error make {msg: 'Invalid Dirpick action: directory is unavailable'}
    }
    cd $destination
}
