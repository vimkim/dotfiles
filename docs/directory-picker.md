# Shared directory picker

`c` in Nushell and Zsh browses immediate child directories using the shared
Python script, `dir-picker`. The parent entry (`../`) comes first, followed by
child directories ordered by modification time, newest first. Hidden
directories and symlinks to directories are included; regular files and
dangling links are not. A directory symlink uses its target directory's
modification time while preserving the symlink path for navigation.

Rows show human-readable directory entry size, local modification date/time,
a directory icon, the name, and any symlink target. Size is the directory's
entry storage, not the total size of its contents. A directory's modification
time can change when direct entries are added, removed, or renamed; editing
an existing file's contents may leave it unchanged.

Typing fuzzy-matches only the directory's name and ranks by matching score.
Dates, sizes, icons, ancestor paths, and symlink target text are excluded from
matching. Equal scores retain recency order; clearing the query restores the
initial order. Normal fzf smart-case and extended syntax are available, such
as `foo bar`, `^foo`, `bar$`, and `!old`. Spaces-only queries behave as empty;
negative-only queries keep input order because their scores tie. There is no
manual sorting toggle.

The interface uses the file picker's 60% height, reverse layout, and colors.
Escape or Ctrl-C cancels without changing directories. Successful navigation
still displays the shell's existing listing (`ezam` in Nushell, `my-list-long`
in Zsh). Nushell's `cl` exposes the same interface as its `c` alias.

## Nushell commands

```nu
c                               # browse the current directory
c ~/projects                    # navigate directly, as before
c --query project               # browse with an initial name query
c ~/projects --query '^work'     # browse inside ~/projects with initial text
c --query ''                    # explicitly browse with an empty query
```

The presence of `--query` selects picker mode even when its value is empty.
Without the option, `c PATH` keeps direct navigation, including special cd
targets such as `-`. The existing Zsh wrapper receives the shared picker UI
and ordering changes; its positional arguments still navigate directly.

## Reuse

Python 3.9 or later and fzf with `--accept-nth` support are required. eza and
GNU stat are not required by the picker. A Nerd Font displays the folder icon.
The script prints a selected absolute path; the shell wrapper changes its own
working directory.

```sh
dir-picker                      # browse the current directory
dir-picker ~/projects           # browse another directory
dir-picker --query project       # initial name query
dir-picker ~/projects --query '^work'
dir-picker --query=-draft        # query text beginning with a dash
dir-picker --list                # unfiltered ordered paths, without fzf
dir-picker --list --json         # JSON array for structured consumers
dir-picker --json                # one JSON string; used by Nushell
dir-picker --null                # one NUL-terminated path; used by Zsh
dir-picker --help
```

JSON and NUL output preserve spaces, tabs, Unicode, and newlines in names.
fzf receives NUL-framed rows with separate metadata and name fields, and
returns an opaque identifier which Python maps back to the actual path.
Backslashes and control characters are escaped only for display and matching;
paths retain their original bytes and symlinks. Line output is intended for
ordinary names; use JSON or NUL framing for scripts.

Equal modification times sort by name. An unavailable browsing root is an
error; children that disappear or become inaccessible during enumeration are
skipped. Exit codes are 0 for a selection/list, 1 for no selection, 130 for
interruption, 127 for missing fzf, and 2 for directory or picker errors. Errors
go to stderr; stdout contains only paths. `--list` works without fzf and
always lists the unfiltered recency order.

## Managed files

| Chezmoi source | Exact deployed target |
| --- | --- |
| `private_dot_config/my-scripts/bin/executable_dir-picker` | `/home/vimkim/.config/my-scripts/bin/dir-picker` |
| `private_dot_config/nushell/alias.nu` | `/home/vimkim/.config/nushell/alias.nu` |

The Zsh wrapper at `private_dot_config/my-scripts/zsh/aliases.zsh`, deployed as
`/home/vimkim/.config/my-scripts/zsh/aliases.zsh`, is covered by regression
checks and does not need source edits. Both shells already put the scripts
directory on PATH. Documentation and verification files are excluded from
chezmoi deployment. Verify and apply each concrete target separately when
deployment is requested.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_directory_picker.py -v
zsh -n private_dot_config/my-scripts/zsh/aliases.zsh
```

Tests exercise the public CLI, actual fzf terminal selection, and Nushell/Zsh
navigation. They cover modification-time order, symlink target times,
inclusion rules, empty → typed → cleared queries, equal-score ordering,
metadata visibility and exclusion, initial queries, cancellation, dependencies,
and unusual-name round trips. They do not inspect private candidate structures.

The fzf scoring scheme must precede `--tiebreak=index`: selecting a scheme
resets its tie-break criteria. The equal-score regression protects this order.
