# Listing helper family

Ten standalone command names share a Python 3 script backed by eza.
They work from Nushell, Bash, and Zsh. Python 3 is required.
The seven sorted commands require eza, and less enables their automatic paging.
`ls-one-page`, `ls-full`, and `lsf` use system `ls` when eza is unavailable.

Bash and Zsh keep `ls` unaliased, including after shell framework initialization.
Use `l` for the bounded preview and `ls-full` or `lsf` for the complete view.

## Commands

| Command | Default view |
| --- | --- |
| `ls-by-name` | Names A–Z, using eza’s case-insensitive natural name order |
| `ls-by-size` | Largest first; ordinary entry sizes, no recursive totals |
| `ls-by-time` | Most recently modified first |
| `ls-by-extension` | Extension, then name |
| `ls-tree` | Alphabetical tree, two levels deep |
| `ls-dirs` | Directories only, alphabetical |
| `ls-files` | Files only, alphabetical |
| `ls-one-page` | Detailed grid within 70% of the terminal height, most recently modified first |
| `ls-full`, `lsf` | Complete listing, most recently modified first, grid in terminals, without a pager |

Every command shows details and hidden entries, without grouping directories
before or after files. `c`, `l`, and `sl` use `ls-one-page` in all three shells.
The filters and handling
of symlinks follow eza; use `--show-symlinks` when needed with filtered views.

```sh
ls-by-size
ls-by-time ~/Downloads
ls-by-size --reverse          # smallest first
ls-by-name --no-pager         # keep output in terminal scrollback
ls-tree --level=3 ~/projects
ls-files --git-ignore
ls-by-name -- ./-unusual-name
ls-by-name --help
ls-one-page ~/Downloads      # also available as l ~/Downloads
ls-full ~/Downloads          # show every entry without a pager
lsf ~/Downloads              # short standalone name for ls-full
```

Paths and eza options are accepted. `-r` / `--reverse` reverses the helper’s
default direction. Other eza options override presets according to eza’s normal
option rules; changing the sort field preserves the helper’s direction unless
you also reverse it. `-h` remains eza’s column-header option. Use `--help` or
`-?` for help. With no path, the current directory is listed even in scripts;
`--stdin` explicitly enables reading paths from standard input.

## One screen for c and l

`ls-one-page` sorts all entries by modification time before limiting output.
Files and directories share the same order, with the newest entry first.
The eza view shows size, relative modification time, icons, and Git state.
Hidden entries are included. Nushell's `ezam` delegates to this helper.
Bash and Zsh call it from their shared `l` function.

The default terminal view arranges eza's detailed entries in multiple columns
when they fit. Read entries down each column before the next column.
The helper chooses the largest prefix of the newest entries that fits,
including space for the notice. Narrow terminals and wide names use a single
column with wrapping. Eza supplies each entry's details, colors, and icons.
The helper arranges those entries to preserve the height limit and exact count.
Use `-1` for an explicit single-column view.

When stdout is a terminal, the helper measures that terminal's height and width.
It accounts for wrapped rows, wide Unicode characters, colors, and hyperlinks.
The listing uses at most 70% of the terminal height, rounded down to whole rows.
If entries do not fit, the helper includes this notice within that limit:

```text
... 700 entries skipped. Run ls-full or lsf to view all.
```

The count includes omitted files, directories, and symlinks, including entries
removed from the preview to make room for the notice. The helper counts output
it already reads, without another directory scan. It buffers only enough
candidate entries to fill the terminal's available area.
Custom layouts and multiple paths report omitted output lines instead of entries.

Short listings have no notice. `ls-full` and `lsf` show every entry in the same order.
Their default terminal view uses eza's full grid without a height limit.
Use the same paths and filters with `ls-full` to expand a specific listing.
Pipes, redirection, and `--no-pager` also receive complete output.
Neither command starts less. System `ls` provides a simpler detailed view
when eza is unavailable. Additional options must match the selected backend.

## Paging for the seven sorted commands

When both stdin and stdout are terminals and TERM is set to a usable terminal
type, output goes through `less -FRX`. Short listings exit automatically and
remain visible. Long listings support scrolling and searching; press `q` to
leave. Wide rows wrap, so a few long names can still fill a screen.

This applies to interactive login and non-login shells and to scripts attached
to a terminal. Parent-shell interactivity is not separately inspected. Pipes,
redirection, `--no-pager`, a missing or dumb TERM, and unavailable less all use
direct output. A missing eza produces a clear error.

Colors are preserved while paging, respecting `NO_COLOR` unless explicitly
overridden with an eza option. The helper clears `LESS` only in the pager child
so user settings cannot turn off wrapping or short-output exit. It always uses
less for these screen-fit semantics, rather than `$PAGER`. There is no listing
length cap and no manual newline-based screen estimate.

## Managed files

| Chezmoi source | Deployed target |
| --- | --- |
| `private_dot_config/my-scripts/bin/executable_ls-by-name` | `~/.config/my-scripts/bin/ls-by-name` |
| `private_dot_config/my-scripts/bin/symlink_ls-by-size` | `~/.config/my-scripts/bin/ls-by-size` |
| `private_dot_config/my-scripts/bin/symlink_ls-by-time` | `~/.config/my-scripts/bin/ls-by-time` |
| `private_dot_config/my-scripts/bin/symlink_ls-by-extension` | `~/.config/my-scripts/bin/ls-by-extension` |
| `private_dot_config/my-scripts/bin/symlink_ls-tree` | `~/.config/my-scripts/bin/ls-tree` |
| `private_dot_config/my-scripts/bin/symlink_ls-dirs` | `~/.config/my-scripts/bin/ls-dirs` |
| `private_dot_config/my-scripts/bin/symlink_ls-files` | `~/.config/my-scripts/bin/ls-files` |
| `private_dot_config/my-scripts/bin/symlink_ls-one-page` | `~/.config/my-scripts/bin/ls-one-page` |
| `private_dot_config/my-scripts/bin/symlink_ls-full` | `~/.config/my-scripts/bin/ls-full` |
| `private_dot_config/my-scripts/bin/symlink_lsf` | `~/.config/my-scripts/bin/lsf` |
| `private_dot_config/my-scripts/shell/productivity.sh` | `~/.config/my-scripts/shell/productivity.sh` |
| `private_dot_config/nushell/eza.nu` | `~/.config/nushell/eza.nu` |

The nine symlinks resolve to `ls-by-name` in the same directory.
`lsf` points to `ls-full`, which points to `ls-by-name`.
The script selects the preset by its invoked name.
All three shells include the scripts directory on PATH.
Repository documentation and tests are excluded from chezmoi deployment.

Commit changes for review in a sibling task worktree.
Follow the [repository workflow](../AGENTS.md) for merge approval and deployment.
After an approved merge, run `chezmoi-apply-unmodified` once for all managed
files and symlinks. Verify affected targets and report any skips.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_ls_helpers.py -v
bash -n dot_bashrc
bash -n private_dot_config/my-scripts/shell/productivity.sh
zsh -n private_dot_config/my-scripts/shell/productivity.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_shell_productivity.py -v
```

The integration suite uses real eza and less. It checks sort directions,
reversal, global ordering, filters, tree depth overrides, hidden entries,
450-entry output, option-like filenames, default paths, explicit stdin,
missing dependencies, errors, and shell pipelines. A 12-row PTY verifies
short-output exit, long and wrapped-output paging, quitting, and paging bypasses.
Shell-specific checks run for installed Bash, Zsh, and Nushell.
Preview checks cover globally sorted files and directories, a 450-entry
directory, exact screen fits, wrapped Unicode names, ANSI colors and hyperlinks,
system `ls` fallback, complete output, errors, and actual `c` and `l` calls
in all three shells. Height checks use 12-row, 20-row, and 40-row terminals.
Count checks cover singular wording, symlinks, wrapped names, fallback totals,
and custom layouts. `ls-full` and `lsf` work through shell pipelines and in terminals.
Grid checks verify multiple columns, the newest-entry prefix, quoted Unicode
names, colors, hyperlinks, narrow terminals, and all three shell shortcuts.
