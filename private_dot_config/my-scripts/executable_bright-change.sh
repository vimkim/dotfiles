#!/bin/bash

# Define brightness levels (in percentages)
levels=("10%" "20%" "30%" "40%" "50%" "60%" "70%" "80%" "90%" "100%")

# Show fzf interface to select brightness level
selected_level=$(printf "%s\n" "${levels[@]}" | fzf --prompt="Select brightness: " --height 40% --reverse)

# If a level is selected, apply it
if [[ -n "$selected_level" ]]; then
  sudo brightnessctl set "$selected_level"
  echo "Brightness set to $selected_level"
else
  echo "No brightness level selected."
fi
