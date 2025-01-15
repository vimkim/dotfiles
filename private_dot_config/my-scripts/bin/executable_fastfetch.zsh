#!/usr/bin/env zsh

# Function to detect OS and set OS_COLOR
set_os_color() {
  case "$(uname -s)" in
    Linux)
      OS_COLOR="blue"  # Default color for Linux systems
      if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
          centos) OS_COLOR="yellow" ;;
          rocky) OS_COLOR="green" ;;
          arch) OS_COLOR="cyan" ;;
          ubuntu) OS_COLOR="red" ;;
          fedora) OS_COLOR="blue" ;;
          *) OS_COLOR="green" ;;  # Fallback for other Linux distros
        esac
      fi
      ;;
    Darwin)
      OS_COLOR="silver"  # macOS
      ;;
    CYGWIN*|MINGW*|MSYS*)
      OS_COLOR="purple"  # Windows with Unix-like environment
      ;;
    *)
      OS_COLOR="white"  # Unknown OS
      ;;
  esac
}

# Call the function to set OS_COLOR
set_os_color

# Run the fastfetch command with detected OS color
fastfetch -l blackarch --logo-color-3 black --logo-color-1 "$OS_COLOR" --logo-color-2 "$OS_COLOR" --color "$OS_COLOR"
