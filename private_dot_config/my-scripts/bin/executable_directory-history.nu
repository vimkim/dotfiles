#!/usr/bin/env -S nu --no-config-file

# Reuse the Nushell history implementation; the calling shell performs the cd.
def --env cl [dir: string] {
    $dir | save --raw --force $env.DIRECTORY_HISTORY_OUTPUT
}
source ~/.config/nushell/dir-history.nu

def main [
    --record: string # Record a directory without opening the picker
    --output: path # Write the selected path separately from picker messages
    --forget (-f)
    --delete (-d)
    --prune (-p)
] {
    if $record != null {
        _dir_history_init
        _dir_history_load | prepend $record | _dir_history_save
        return
    }

    if $output == null {
        error make {msg: "directory-history.nu requires --output or --record"}
    }
    $env.DIRECTORY_HISTORY_OUTPUT = $output
    cd-dir-history --forget=$forget --delete=$delete --prune=$prune
}
