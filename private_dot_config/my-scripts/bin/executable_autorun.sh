#!/usr/bin/env bash

proj_type=$(detect-project.sh)

case "$proj_type" in
    rust|go|python|cmake|cpp|c)
        justfile="$HOME/.config/my-scripts/$proj_type.just"
        ;;
    *)
        echo "Unsupported project type: $proj_type" >&2
        exit 1
        ;;
esac

recipe=$(just-pick-and-print.nu -f "$justfile" -d . | tr -d '\n')
if [[ -n $recipe ]]; then
    printf 'just -f %q -d . %q\n' "$justfile" "$recipe"
fi
