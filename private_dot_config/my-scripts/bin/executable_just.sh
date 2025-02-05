#!/usr/bin/env bash
set -euo pipefail

# Function to display usage information.
usage() {
    cat <<EOF
Usage: $(basename "$0") [-h] [-j JUSTFILE] [-d JUST_DIR]

Options:
  -h              Show this help message and exit.
  -j JUSTFILE     Path to the justfile.
                  Default: "\${MY_CUBRID:-/path/to/default/dir}/remote/justfile"
  -d JUST_DIR     Path to the directory containing the justfile.
                  Default: "\${MY_CUBRID:-/path/to/default/dir}/remote"
EOF
}

# Parse command-line options.
while getopts "hj:d:" opt; do
    case "$opt" in
    h)
        usage
        exit 0
        ;;
    j)
        JUSTFILE="$OPTARG"
        ;;
    d)
        JUST_DIR="$OPTARG"
        ;;
    \?)
        usage
        exit 1
        ;;
    esac
done

# Remove parsed options from the positional parameters.
shift $((OPTIND - 1))

# Validate the provided justfile and directory.
if [ ! -f "$JUSTFILE" ]; then
    echo "Error: Justfile not found at '$JUSTFILE'" >&2
    exit 1
fi

if [ ! -d "$JUST_DIR" ]; then
    echo "Error: Just directory not found at '$JUST_DIR'" >&2
    exit 1
fi

# Define the chooser command with a preview that uses the specified justfile and directory.
CHOOSER=(fzf --reverse --multi --height 50% --preview "just -f '$JUSTFILE' -d '$JUST_DIR' --unstable --color always --show {}")

# List available recipes from the justfile.
# The '--summary' option lists the recipes; adjust the 'tr' conversion if your recipe names contain spaces.
recipes=$(just -f "$JUSTFILE" -d "$JUST_DIR" --summary | tr ' ' '\n')

# Run the chooser and capture the selected recipe(s).
CMD=$(printf '%s\n' "$recipes" | "${CHOOSER[@]}")

# If no selection was made, exit silently.
if [ -z "$CMD" ]; then
    exit 0
fi

# Run a dry-run with the selected recipes for verification.
dry_run_output=$(just -f "$JUSTFILE" -d "$JUST_DIR" --dry-run $CMD 2>&1 | sed '$!s/$/ \&\&/')

# Output the dry-run commands.
# You can modify this part to integrate with your shell's command line replacement (e.g., using zsh's print -z).
printf '%s\n' "$dry_run_output"
