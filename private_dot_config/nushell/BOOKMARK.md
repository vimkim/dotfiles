# Shared directory bookmarks

`dir-bookmark` is a Python 3 command that owns named directory bookmarks for
Bash, Zsh, and Nushell. Shell adapters expose `bm` and change the calling shell's
working directory. `bookmark.nu` contains only the Nushell adapter.

## Everyday commands

| Command | Action |
| --- | --- |
| `bm` | Pick a bookmark with fzf, enter it, and list its contents. |
| `bm NAME` | Enter a bookmark by its exact name. |
| `bm add [NAME] [PATH]`, `ba [NAME] [PATH]` | Save PATH, defaulting to the current directory; NAME defaults to its basename. |
| `bm add NAME PATH --replace` | Update an existing name to a different directory. |
| `bm del [NAME ...]`, `bd [NAME ...]` | Remove named bookmarks, or select multiple with fzf when no names are supplied. |
| `bm list`, `bl` | List bookmarks; Nushell returns records and Bash/Zsh print name/path lines. |
| `bm pick NAME` | Enter a name that would otherwise be a management command, such as `add`. |
| `bm -a`, `bm -d`, `bm a`, `bm d`, `bm l` | Compatibility forms for add, delete, and list. |

Zsh's existing `cb` shortcut also opens `bm`.

Bookmarks have unique, case-sensitive names. Adding the same name and path is
idempotent. Reusing a name for another path requires `--replace`; multiple names
can refer to the same directory. Missing directories are reported and their
bookmarks are kept. Removing a bookmark never removes the directory itself.
Cancelling a picker leaves the current directory and bookmarks unchanged.

## Fixed directory shortcuts

These aliases are available in all three shells:

| Command | Destination |
| --- | --- |
| `dir-chez` | `~/.local/share/chezmoi` |
| `dir-gh` | `~/gh` |
| `dir-works` | `~/works` |
| `dir-tmp`, `tmpd` | The current `TMPDIR` value. |

These shortcuts do not depend on saved bookmarks. A saved bookmark records an
absolute path; `dir-tmp` follows environment changes instead.

## Storage and migration

Bookmarks live in `$XDG_DATA_HOME/dir-bookmark/bookmarks.json`, defaulting to
`~/.local/share/dir-bookmark/bookmarks.json`. An empty or relative XDG_DATA_HOME
is ignored. This is shared per user across shells, separately from shell config.

The [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/)
uses XDG_DATA_HOME for user data. XDG_STATE_HOME, defaulting to ~/.local/state,
is intended for history and session state. Deliberately saved bookmarks belong
in the data directory.

The versioned JSON file contains a list of `{name, path}` records. The store uses
an advisory lock and atomic replacement to preserve concurrent edits by multiple
shells. New application directories have mode 0700 and files have mode 0600.
Malformed or unsupported data produces an error and is left unchanged.

On the first operation needing storage, the CLI imports `~/.bookmarks.nuon` if it
exists. The original file remains unchanged as a backup. Duplicate legacy names
receive `-2`, `-3`, etc. suffixes so every record survives. Initializing storage
is the migration marker: later runs do not reimport removed bookmarks.
Malformed legacy input prevents initialization and remains untouched.

Nushell is required only for this one-time NUON conversion. Normal CLI use has
no Nushell dependency. fzf is required for interactive selection, and is not
needed for direct named jumps, adds, lists, or named removals.

Run migration explicitly after deployment:

```sh
dir-bookmark migrate
dir-bookmark path
dir-bookmark list --json
```

## CLI and shell adapters

The executable prints destinations; `bm` performs `cd` in the calling shell.

```sh
dir-bookmark add chez ~/.local/share/chezmoi
dir-bookmark add gh ~/gh
dir-bookmark add works ~/works
dir-bookmark pick chez
dir-bookmark pick --json
dir-bookmark pick --null
dir-bookmark delete chez
dir-bookmark --help
```

`pick --json` returns one path string, or null on empty selection/cancellation.
`pick --null` preserves all path characters using NUL framing. Picker rows use
stable indices, so escaped tabs/newlines in display text never become paths.
Unknown names, missing destinations, invalid data, and failed commands return
nonzero. Empty selection/cancellation returns success without a destination.

Reload existing Bash/Zsh sessions after deployment:

```sh
source ~/.config/my-scripts/shell/productivity.sh
```

Reload existing Nushell sessions:

```nu
source ~/.config/nushell/alias.nu
```

New interactive sessions load the adapters automatically.

## Verification

```sh
python3 -B -m unittest discover -s tests -p test_dir_bookmark.py -v
python3 -B -m unittest discover -s tests -p test_shell_productivity.py -v
bash -n private_dot_config/my-scripts/shell/productivity.sh
zsh -n private_dot_config/my-scripts/shell/productivity.sh
```
