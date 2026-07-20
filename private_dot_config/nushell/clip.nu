# Copy pipeline input to the platform clipboard.
def clip [] {
  let input = $in
  let os_name = $nu.os-info.name
  let is_wsl = if $os_name == "linux" {
    ($env.WSL_DISTRO_NAME? | is-not-empty) or (
      ('/proc/version' | path exists) and
      (open /proc/version | str lowercase | str contains "microsoft")
    )
  } else {
    false
  }

  if $is_wsl {
    if (which clip.exe | is-empty) {
      error make "Error: 'clip.exe' is not installed"
    }
    $input | clip.exe
  } else if $os_name == "linux" {
    let is_wayland = (
      ($env.WAYLAND_DISPLAY? | is-not-empty) or
      (($env.XDG_SESSION_TYPE? | default "" | str lowercase) == "wayland")
    )

    if $is_wayland and (which wl-copy | is-not-empty) {
      $input | wl-copy
    } else if (which xclip | is-not-empty) {
      $input | xclip -selection clipboard
    } else if (which wl-copy | is-not-empty) {
      error make "Error: 'wl-copy' is installed, but no Wayland session was detected and 'xclip' is not installed"
    } else {
      error make "Error: neither 'xclip' nor 'wl-copy' is installed"
    }
  } else if $os_name == "windows" {
    if (which clip.exe | is-empty) {
      error make "Error: 'clip.exe' is not installed"
    }
    $input | clip.exe
  } else if $os_name == "macos" {
    if (which pbcopy | is-empty) {
      error make "Error: 'pbcopy' is not installed"
    }
    $input | pbcopy
  } else {
    error make $"Unsupported OS: ($os_name)"
  }
}
