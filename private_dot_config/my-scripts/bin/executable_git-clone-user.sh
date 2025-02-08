#!/bin/bash
set -euo pipefail

# Ensure a GitHub username is provided.
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <github-username>"
    exit 1
fi

username="$1"
# GitHub API URL: sort repositories by recent update, limit to 30.
api_url="https://api.github.com/users/${username}/repos?sort=updated&direction=desc&per_page=30"

echo "Fetching repositories for user '$username'..."
# Fetch JSON data from GitHub.
repo_json=$(curl -s "$api_url")

# Check if the returned JSON is an object with a "message" key (indicating an error).
if echo "$repo_json" | jq -e 'if type=="object" and has("message") then .message else empty end' >/dev/null; then
    error_message=$(echo "$repo_json" | jq -r '.message')
    echo "Error fetching repositories: $error_message"
    exit 1
fi

# Parse the JSON to produce a tab-separated list:
# Full Repository Name (<username>/<repo>), Updated Date, and Clone URL.
repos=$(echo "$repo_json" | jq -r '.[] | "\(.full_name)\t\(.updated_at)\t\(.clone_url)"')

if [ -z "$repos" ]; then
    echo "No repositories found for user '$username'."
    exit 0
fi

# Let the user fuzzily select a repository using fzf.
echo "Select a repository to clone (fuzzy search enabled):"
selected=$(echo "$repos" | fzf --with-nth=1,2 --delimiter="\t" --height=40%)

if [ -z "$selected" ]; then
    echo "No repository selected. Exiting."
    exit 0
fi

# Extract the full repository name and clone URL from the selected line.
repo_full_name=$(echo "$selected" | awk -F '\t' '{print $1}')
clone_url=$(echo "$selected" | awk -F '\t' '{print $3}')

# In our case, the repository identifier is already in the form <username>/<reponame>.
REPO_URL="$repo_full_name"

# Get the repository's size in KB.
REPO_SIZE=$(curl -s "https://api.github.com/repos/$REPO_URL" | jq '.size')

# Check if REPO_SIZE is null or empty.
if [[ -z "$REPO_SIZE" || "$REPO_SIZE" == "null" ]]; then
    echo "Error: Unable to fetch repository size for '$REPO_URL'."
    exit 1
fi

# Convert the size to MB (using bc for floating-point division).
HUMAN_SIZE=$(echo "scale=2; $REPO_SIZE / 1024" | bc)

echo "Repository: $REPO_URL"
echo "Repository size: $HUMAN_SIZE MB"

# Prompt the user for confirmation to clone.
read -r -p "Clone repository '$repo_full_name'? (y/n): " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "Cloning $repo_full_name from $clone_url..."
    git clone "$clone_url"
else
    echo "Clone aborted."
fi
