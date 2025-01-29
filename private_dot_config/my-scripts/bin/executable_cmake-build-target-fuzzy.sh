#!/usr/bin/env bash

# cmakerun - Interactive CMake target selector
# Usage: ./cmakerun.sh [build_dir] [--phony|--custom|--all]

set -euo pipefail

# Default values
BUILD_DIR="build"
FILTER_TYPE="all"
PREVIEW_LINES=3

show_help() {
    echo "Usage: $0 [OPTIONS] [BUILD_DIR]"
    echo
    echo "Interactive CMake target selector"
    echo
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -p, --phony         Show only phony targets"
    echo "  -c, --custom        Show only custom command targets"
    echo "  -a, --all           Show all targets (default)"
    echo "  --preview-lines N   Number of preview lines (default: 3)"
    echo
    echo "Arguments:"
    echo "  BUILD_DIR           CMake build directory (default: 'build')"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
    -h | --help)
        show_help
        exit 0
        ;;
    -p | --phony)
        FILTER_TYPE="phony"
        shift
        ;;
    -c | --custom)
        FILTER_TYPE="custom"
        shift
        ;;
    -a | --all)
        FILTER_TYPE="all"
        shift
        ;;
    --preview-lines)
        PREVIEW_LINES="$2"
        shift 2
        ;;
    *)
        BUILD_DIR="$1"
        shift
        ;;
    esac
done

# Check if build directory exists
if [[ ! -d "$BUILD_DIR" ]]; then
    echo "Error: Build directory '$BUILD_DIR' does not exist"
    exit 1
fi

# Get target list and apply filtering
get_targets() {
    local targets
    targets=$(cmake --build "$BUILD_DIR" --target help | tail -n +2)

    case "$FILTER_TYPE" in
    "phony")
        echo "$targets" | grep ': phony'
        ;;
    "custom")
        echo "$targets" | grep 'CUSTOM_COMMAND'
        ;;
    *)
        echo "$targets"
        ;;
    esac
}

# Extract just the target name (everything before the colon)
format_target() {
    sed -E 's/^[[:space:]]*([^:]+):.*/\1/'
}

# Get and process targets
targets=$(get_targets | format_target)

if [[ -z "$targets" ]]; then
    echo "No targets found matching the specified criteria"
    exit 1
fi

# Select target using fzf
selected_target=$(echo "$targets" | fzf \
    --preview "cmake --build $BUILD_DIR --target help | grep -A $PREVIEW_LINES {}" \
    --preview-window="up:$PREVIEW_LINES:wrap" \
    --height=80% \
    --border=rounded \
    --prompt="Select target > ")

if [[ -n "$selected_target" ]]; then
    # Run the selected target
    echo "Running target: $selected_target"
    cmake --build "$BUILD_DIR" --target "$selected_target"
else
    echo "No target selected"
    exit 0
fi
