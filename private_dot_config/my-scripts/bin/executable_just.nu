#!/usr/bin/env nu

def main [
    --justfile (-f): path
    --justdir  (-d): path
] {
    # usage helper
    def usage [] {
        print -e "Usage: ./just.nu -f <justfile> -d <justdir>"
        exit 1
    }

    # Nushell will set $justfile / $justdir to `null` if not provided
    if ($justfile == null or $justdir == null) {
        usage
    }

    # At this point both flags are provided:

    # Sanity checks
    if not ($justfile | path exists) {
        print -e $"Error: justfile not found at '{justfile}'"
        exit 1
    }
    if not ($justdir | path exists) {
        print -e $"Error: remote directory not found at '{justdir}'"
        exit 1
    }

    # List recipes
    let recipes = (just -f $justfile -d $justdir --summary | split row ' ' | str join (char nl))
    if ($recipes | is-empty) {
        print -e "No recipes found."
        exit 1
    }

    let preview_cmd = $"just -f ($justfile) -d ($justdir) --unstable --color always --show {}"

    # Fuzzy-select
    let chosen = (
        $recipes
        | fzf --reverse --height 80% --preview $preview_cmd --preview-window=right:60%
        | str trim
    )

    if ($chosen | is-empty) {
        exit 0
    }

    just -f $justfile -d $justdir --dry-run $chosen | complete | get stderr

}
