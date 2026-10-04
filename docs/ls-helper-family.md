# Listing helper family

Seven standalone command names share a Python 3 script backed by eza. They work
from Nushell, Bash, and Zsh without shell-specific functions. Python 3 and eza
are required; less enables automatic paging.

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

Every command shows details and hidden entries, without grouping directories
before or after files. Existing aliases are unchanged. The filters and handling
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
```

Paths and eza options are accepted. `-r` / `--reverse` reverses the helper’s
default direction. Other eza options override presets according to eza’s normal
option rules; changing the sort field preserves the helper’s direction unless
you also reverse it. `-h` remains eza’s column-header option. Use `--help` or
`-?` for help. With no path, the current directory is listed even in scripts;
`--stdin` explicitly enables reading paths from standard input.

## Paging

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
| `dot_bashrc` | `~/.bashrc` |

The six symlinks point to `ls-by-name` in the same directory. The script selects
the preset by its invoked name. Bash gains the scripts directory on PATH;
Nushell and Zsh already include it. Repository documentation and tests are
excluded from chezmoi deployment.

Changes are committed for review in a sibling task worktree. Merge approval
and explicit deployment authorization follow the repository workflow. When
deployment is requested, verify and apply the script target first, then each
symlink target and Bash configuration individually; never use a broad apply.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_ls_helpers.py -v
bash -n dot_bashrc
```

The integration suite uses real eza and less. It checks sort directions,
reversal, global ordering, filters, tree depth overrides, hidden entries,
450-entry output, option-like filenames, default paths, explicit stdin,
missing dependencies, errors, and shell pipelines. A 12-row PTY verifies
short-output exit, long and wrapped-output paging, quitting, and paging bypasses.
Shell-specific checks run for installed Bash, Zsh, and Nushell.
