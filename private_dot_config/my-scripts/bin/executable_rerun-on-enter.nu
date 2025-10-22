#!/usr/bin/env nu

# Usage: rerun-on-x <command ...>
# Example: rerun-on-x cargo run

def main [...cmd] {
    if ($cmd | is-empty) {
        print "Usage: rerun-on-x <command ...>"
        exit 2
    }

    while true {
        # run the external command with its arguments
        run-external $cmd.0 ...($cmd | skip 1)

        print $"($cmd) finished."
        let k = (input "Press enter to run again (q to quit):")
        if $k == "q" { break }
    }
}

