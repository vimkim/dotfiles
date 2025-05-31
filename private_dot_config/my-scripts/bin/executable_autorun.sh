#!/usr/bin/env bash

proj_type=$(detect-project.sh)

if [[ $proj_type == "rust" ]]; then
    just.nu -f ~/.config/my-scripts/rust.just -d .
elif [[ $proj_type == "go" ]]; then
    just.nu -f ~/.config/my-scripts/go.just -d .
elif [[ $proj_type == "python" ]]; then
    just.nu -f ~/.config/my-scripts/python.just -d .
elif [[ $proj_type == "cmake" ]]; then
    just.nu -f ~/.config/my-scripts/cmake.just -d .
else
    echo "Unsupported project type: $proj_type"
fi
