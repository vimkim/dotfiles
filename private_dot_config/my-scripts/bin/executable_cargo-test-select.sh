#!/bin/bash
# select_test_fzf.sh
#
# This script retrieves a list of cargo test targets, uses fzf for fuzzy selection,
# and then runs the chosen test.
#
# Requirements:
#   - cargo
#   - rg (ripgrep)
#   - awk
#   - fzf
#
# Usage:
#   ./select_test_fzf.sh

# Get the list of tests:
# 1. 'cargo test -- --list --format=terse 2>/dev/null' outputs all tests in terse format.
# 2. 'rg 'test$'' filters only the lines that end with "test".
# 3. 'awk -F':' '{print $1}'' extracts the test names (everything before the colon).
tests=$(cargo test -- --list --format=terse 2>/dev/null | rg 'test$' | awk -F':' '{print $1}')

# Check if any tests were found.
if [[ -z "$tests" ]]; then
    echo "No tests found."
    exit 1
fi

# Use fzf to allow fuzzy selection of a test target.
selected=$(echo "$tests" | fzf --prompt="Select a test: ")

# Verify that a selection was made.
if [[ -z "$selected" ]]; then
    echo "No test selected. Exiting."
    exit 1
fi

echo "Running test: $selected"
cargo test "$selected"
