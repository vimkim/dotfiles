# bookmark.nu

Directory bookmark manager for Nushell with fzf TUI picker.

## Dependencies

- `fzf` - interactive fuzzy finder
- `cl` - custom cd+ls function defined in `alias.nu`

## Data

Bookmarks stored in `~/.bookmarks.nuon` as a list of `{name, path}` records.

## Commands

| Command         | Alias | Description                                      |
|-----------------|-------|--------------------------------------------------|
| `bm`            |       | fzf picker -> cd to selected bookmark            |
| `bm add [name]` | `ba`, `bm a` | Bookmark current dir (name defaults to basename) |
| `bm del`        | `bd`, `bm d` | fzf multi-select picker -> delete selected       |
| `bm list`       | `bl`, `bm l` | Print all bookmarks as table                     |
| `bm -a`         |       | Shorthand for `bm add`                           |
| `bm -d`         |       | Shorthand for `bm del`                           |

Aliases `ba`, `bd`, `bl` are defined in `alias.nu`.

## Internals

| Function     | Purpose                                            |
|--------------|----------------------------------------------------|
| `_bm_load`   | Load bookmarks from file (returns `[]` if missing) |
| `_bm_save`   | Save pipeline input to bookmark file               |
| `_bm_fmt`    | Format bookmarks as aligned `name  path` lines     |
| `_bm_parse`  | Extract path from a formatted line                 |

## Behavior

- Duplicate paths are rejected on add.
- Stale bookmarks (deleted directories) are auto-removed when selected in the picker.
- `bm del` supports TAB multi-select in fzf.
- Column alignment is dynamic based on the longest bookmark name.

## Sourced from

`alias.nu` line: `source ~/.config/nushell/bookmark.nu`

Managed via chezmoi at `private_dot_config/nushell/bookmark.nu`.
