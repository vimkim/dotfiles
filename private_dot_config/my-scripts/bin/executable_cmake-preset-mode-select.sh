#!/usr/bin/env bash

set -euo pipefail

# Capture presets safely
presets=$(cmake --list-presets=configure 2>&1) || {
    echo "❌ Failed to list CMake presets:"
    echo "$presets"
    exit 1
}

# Extract preset names
preset_list=$(printf "%s\n" "$presets" \
    | awk '/Available configure presets:/,0' \
    | tail -n +2 \
    | sed 's/"//g' \
    | awk 'NF')

if [[ -z "$preset_list" ]]; then
    echo "❌ No configure presets found."
    exit 1
fi

# Ensure fzf exists
if ! command -v fzf >/dev/null 2>&1; then
    echo "❌ fzf is not installed or not in PATH."
    exit 1
fi

# Run fzf safely
selected=$(printf "%s\n" "$preset_list" | fzf --prompt="Choose preset:") || {
    echo "⚠️  Selection cancelled."
    exit 1
}

if [[ -z "$selected" ]]; then
    echo "❌ No preset selected."
    exit 1
fi

# Write to .env safely
if ! echo "PRESET_MODE=$selected" > .env; then
    echo "❌ Failed to write to .env"
    exit 1
fi

echo "✅ Selected preset: $selected"
echo "📄 Written to .env"

