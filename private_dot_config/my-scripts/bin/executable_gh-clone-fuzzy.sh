#!/bin/bash

# Fetch your repositories using GitHub CLI
repos=$(gh repo list --limit 50 --json nameWithOwner,url | jq -r '.[] | "\(.nameWithOwner)\t\t\t\(.url)"')

# Use fzf to select a repository
selected=$(echo "$repos" | fzf --prompt="Search your repos: " --preview='echo {} | awk "{print \$2}"')

# If a selection is made, clone the repository
if [[ -n "$selected" ]]; then
    repo_url=$(echo "$selected" | awk '{print $2}')
    echo "Cloning $repo_url..."
    git clone "$repo_url"
else
    echo "No repository selected."
fi
