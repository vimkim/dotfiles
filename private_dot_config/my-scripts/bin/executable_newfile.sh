#!/bin/bash

# Use fzf to select a directory
SELECTED_DIR=$(fd . -t d | fzf --prompt="Select a directory: " --height=20 --border)

# Check if a directory was selected
if [ -z "$SELECTED_DIR" ]; then
  echo "No directory selected. Exiting."
  exit 1
fi

# Prompt for the new file name
read -p "Enter the new file name: " FILE_NAME

# Check if a file name was provided
if [ -z "$FILE_NAME" ]; then
  echo "No file name entered. Exiting."
  exit 1
fi

# Create the file in the selected directory
NEW_FILE_PATH="${SELECTED_DIR}/${FILE_NAME}"

if [ -e "$NEW_FILE_PATH" ]; then
  echo "Error: File already exists at ${NEW_FILE_PATH}. Exiting."
  exit 1
fi

touch "$NEW_FILE_PATH"

if [ $? -eq 0 ]; then
  echo "File created at: ${NEW_FILE_PATH}"
else
  echo "Failed to create file. Check permissions."
fi
