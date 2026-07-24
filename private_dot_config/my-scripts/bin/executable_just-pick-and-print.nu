#!/usr/bin/env nu

# just-pick-and-print.nu — fzf-pick a recipe and print its name to stdout.
#
# Unlike just-deprecated.nu, this does not expand the recipe's dry-run command.
# It prints the bare recipe name (e.g. `build`) so the caller can construct an
# editable `just build` command and let shell history record it.
def main [
    --justfile (-f): path
    --justdir  (-d): path
] {
    def usage [] {
        print -e "Usage: just-pick-and-print.nu -f <justfile> -d <justdir>"
        exit 1
    }

    # Nushell sets these to `null` when the flag is omitted.
    if ($justfile == null or $justdir == null) {
        usage
    }

    if not ($justfile | path exists) {
        print -e $"just-pick-and-print.nu error: file not found: ($justfile)"
        exit 1
    }
    if not ($justdir | path exists) {
        print -e $"just-pick-and-print.nu error: directory not found: ($justdir)"
        exit 1
    }

    # `--summary` is a space-separated list of recipe names.
    let recipes = (just -f $justfile -d $justdir --summary | split row ' ' | str join (char nl))
    if ($recipes | is-empty) {
        print -e "No recipes found."
        exit 1
    }

    let preview_cmd = $"just -f ($justfile) -d ($justdir) --color always --show {}"

    let chosen = (
        $recipes
        | fzf --reverse --height 80% --preview $preview_cmd --preview-window=right:60%
        | str trim
    )

    # Empty = user cancelled fzf. Print nothing so the caller skips pasting.
    if ($chosen | is-empty) {
        exit 0
    }

    print $chosen
}
