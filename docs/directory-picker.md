# Shared directory picker

`c` in Nushell and Zsh browses immediate child directories using the same
Python script, `dir-picker`. The parent entry (`../`) comes first, followed by
directories in creation-time order, newest first. Hidden directories and
symlinks to directories are included; regular files and dangling links are not.
Symlinks use the creation time of the link itself.

Typing filters the list while preserving time order. Press `Ctrl-S` to toggle
fzf's relevance sorting. Escape or Ctrl-C cancels without changing directories.
`c PATH` still navigates directly, and successful navigation still displays the
shell's existing directory listing (`ezam` in Nushell, `my-list-long` in Zsh).
Nushell's `cl` also uses the shared picker when called without an argument.

## Reuse

Python 3.9 or later and fzf are required. The script prints a selected absolute
path; the shell wrapper changes its own working directory.

```sh
dir-picker                      # browse the current directory
dir-picker ~/projects           # browse another directory
dir-picker --list                # ordered paths, without opening fzf
dir-picker --list --json         # JSON array for structured consumers
dir-picker --json                # one JSON string; used by Nushell
dir-picker --null                # one NUL-terminated path; used by Zsh
dir-picker --help
```

JSON and NUL output preserve spaces, tabs, Unicode, and newlines in names. fzf
receives NUL-delimited labels rather than parsed, decorated `ls` output. Paths
retain symlinks instead of resolving their destinations. Line output is intended
for ordinary names; use JSON or NUL framing for scripts.

The script uses Python's native birth timestamp where available. On Linux it
reads birth timestamps in batches through GNU `stat`, because Python's regular
`os.stat()` does not expose Linux birth time. When birth time or GNU stat is
unavailable, an entry falls back to its modification time. Equal timestamps
sort by name. Metadata change time (`ctime`) is never treated as creation time.
An unavailable browsing root is an error; children that disappear or become
inaccessible during enumeration are skipped.

Exit codes are 0 for a selection/list, 1 for no selection, 130 for interruption,
127 for missing fzf, and 2 for directory or picker errors. Errors go to stderr;
stdout contains only paths. `--list` works without fzf.

## Managed files

| Chezmoi source | Exact deployed target |
| --- | --- |
| `private_dot_config/my-scripts/bin/executable_dir-picker` | `~/.config/my-scripts/bin/dir-picker` |
| `private_dot_config/nushell/alias.nu` | `~/.config/nushell/alias.nu` |
| `private_dot_config/my-scripts/zsh/aliases.zsh` | `~/.config/my-scripts/zsh/aliases.zsh` |

Both shells already put the scripts directory on PATH. These changes do not
require editing their startup files. Documentation and verification files are
excluded from chezmoi deployment. Verify and apply each target separately when
deployment is requested.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_directory_picker.py -v
zsh -n private_dot_config/my-scripts/zsh/aliases.zsh
```

The suite checks real Linux creation time independently of modification time,
fallback ordering, inclusion rules, structured output, real fzf filtering,
cancellation, missing dependencies, and navigation through both shell wrappers.
