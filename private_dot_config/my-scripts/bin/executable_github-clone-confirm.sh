#!/usr/bin/env bash

set -e

# Check for required tool
if ! command -v curl &>/dev/null; then
    echo "curl is required but not installed."
    exit 1
fi

if ! command -v jq &>/dev/null; then
    echo "jq is required but not installed. Install it with: sudo pacman -S jq"
    exit 1
fi

if [ -z "$1" ]; then
    echo "Usage: $0 <github-repo-url>"
    exit 1
fi

repo_url="$1"

# Extract owner and repo from URL
if [[ "$repo_url" =~ github\.com[:/](.+)/(.+?)(\.git)?$ ]]; then
    owner="${BASH_REMATCH[1]}"
    repo="${BASH_REMATCH[2]}"
else
    echo "Invalid GitHub URL"
    exit 1
fi

# Fetch repo metadata
api_url="https://api.github.com/repos/${owner}/${repo}"
echo "Fetching repository info from GitHub..."

repo_info=$(curl -s "$api_url")

# Check for rate limit or error
if echo "$repo_info" | grep -q '"Not Found"'; then
    echo "Repository not found."
    exit 1
fi

size_kb=$(echo "$repo_info" | jq '.size')
size_mb=$(awk "BEGIN {printf \"%.2f\", $size_kb / 1024}")

echo "Repository: $owner/$repo"
echo "Estimated size: ${size_mb} MB"

read -rp "Do you want to clone this repository? [y/N]: " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    git clone "$repo_url"
else
    echo "Aborted."
fi
