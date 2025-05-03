#!/bin/bash

# Read from stdin into a variable
input=$(cat)

# Focus the next pane
# zellij action focus-next-pane
zellij action toggle-floating-panes

# Send input to the newly focused pane
zellij action write-chars "$input"
