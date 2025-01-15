#!/bin/bash

# Show help message if no directory is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <directory_path>"
    echo "Shows the last commit information for all files in the specified directory"
    echo "Example: $0 src/"
    exit 1
fi

# Check if directory exists
if [ ! -d "$1" ]; then
    echo "Error: '$1' is not a directory"
    exit 1
fi

# Find the maximum filename length for alignment
max_length=0
for file in "$1"/*; do
    if [ -d "$file" ]; then
        file="$file/"
    fi
    if [ ${#file} -gt $max_length ]; then
        max_length=${#file}
    fi
done

# Iterate through each file and display the git log in the aligned format
for file in "$1"/*; do
    if [ -d "$file" ]; then
        file="$file/"
    fi
    commit_info=$(git log --follow --color=always -1 --format="%C(green)%cr %C(red)%h%Creset %C(yellow)%as%Creset %C(cyan)%an%Creset %C(white)%s%Creset" -- "$file")
    printf "%-${max_length}s | %s\n" "$file" "$commit_info"
done
