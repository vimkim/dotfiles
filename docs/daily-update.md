# Daily update

`daily-update` is a Python 3.11+ command. Its source launcher is
`private_dot_config/my-scripts/bin/executable_daily-update`, deployed to
`~/.config/my-scripts/bin/daily-update`. It imports the adjacent
`~/.config/my-scripts/daily_update/` package using its own location, so invocation
works from any directory. There are no third-party Python dependencies.

## Feature modules

The launcher delegates to `daily_update/cli.py`. The modules separate these jobs:

- `dotfiles.py`: refresh the configured chezmoi source and deploy through the helper.
- `tools.py`: resolve and upgrade Codex and Claude Code.
- `projects.py`: validate the TOML inventory, refresh checkouts, and run `just sync`.
- `skills.py`: update eligible third-party skills, scan stale skills, and prune recoverably.
- `state.py`: maintain the daily stamp and produce offline reminder/status output.
- `common.py`: execute commands and collect independent step outcomes.

## Personal projects

Edit the managed source `private_dot_config/my-scripts/daily-update.toml`. Its
absolute deployed target is `~/.config/my-scripts/daily-update.toml`, or
`$XDG_CONFIG_HOME/my-scripts/daily-update.toml` when that variable is set.
`daily-update --config /path/to/projects.toml` selects another inventory.

```toml
[[projects]]
name = "my-skills"
path = "~/gh/my-skills"
github = "vimkim/my-skills"
kind = "collection"

[[projects]]
name = "dirpick"
path = "~/gh/dirpick"
github = "vimkim/dirpick"
primary_main = true
```

Projects run in file order. Each entry requires a unique `name`, an absolute
`path` (with `~` expansion), and a GitHub `owner/repository` identity. `kind`
defaults to `tool`; `collection` also protects that project's GitHub identity,
local path, and current skill names from third-party maintenance.
`primary_main` defaults to `false`. When true, it requires a primary checkout
on `main` tracking `origin/main` with the configured GitHub origin; linked
worktrees and symlinks are skipped. Unknown fields, malformed entries, and
duplicate names or paths reject the entire inventory before updates or pruning.
An empty inventory uses `projects = []`.

The supplied list preserves the two skill collections and five personal tools.
Add a project by editing TOML; Python code needs no project-specific entry.
The legacy `DAILY_UPDATE_COLLECTION_ORDER=cubrid-first` override reverses
collection order while retaining their slots in the inventory.

Each project must be an independent Git checkout with no tracked or untracked
changes and a published upstream. Refresh fetches that upstream's remote,
requires HEAD to be an ancestor of the newly fetched upstream, and fast-forwards
with `git merge --ff-only`. Primary-main projects fetch `main` explicitly, so a
deleted remote branch fails instead of authorizing stale installation.
Dirty, ahead, diverged, detached, missing, nested non-checkout and untracked-branch
checkouts are preserved and skipped. Inspection, fetch and merge failures stop
that project's sync while independent work continues.

After refresh, the runner requires a local `justfile` and executes
`just --justfile ./justfile sync` inside that project. The recipe owns installation
and reconciliation. Skill ownership, pruning and recovery stay in the collection
sync engines. Chronicle's recipe reinstalls the CLI; collecting CI evidence
still requires an explicit `cubrid-tcc sync-data` invocation.

## Dotfiles, tools and third-party skills

Normal runs first resolve the dotfiles source with `chezmoi source-path`. It must
be a clean independent checkout on `main` tracking `origin/main` from
`vimkim/dotfiles`. Fetch requests remote `main` explicitly, then an ancestor check
and fast-forward precede `chezmoi-apply-unmodified --source SOURCE`. The helper
runs even when Git is unchanged. Local target edits, deletions and existing files
without last-write history remain preserved and count as partial work. See
[helper behavior](chezmoi-apply-unmodified.md).

Codex and Claude upgrades follow. Resolution prefers `~/.local/bin` across shells.
A Codex executable inside Homebrew's prefix is upgraded with Homebrew only when
its package database confirms the installed cask or formula. Personal projects
then run, followed by third-party maintenance and a stale scan.

Third-party updates use `skills@1.7.0 update NAME ... --global --yes` with an
explicit eligible list. An empty list never becomes a bulk update. Personal
collection identities and name collisions are excluded even when a checkout is
dirty or missing. Invalid lock entries or unreadable source inventories block
maintenance and pruning. Skills absent from the installer lock remain outside
legacy pruning, including dangling unowned links.

A lock-backed skill is stale when its installed directory is missing, its Claude
symlink is broken, or a successful upstream tree query shows that its name was
removed. Failed or unexpected API responses cannot authorize removal. `--prune`
moves installed directories into a unique dated cache trash directory and saves
the original lock file there before updating it. Collection sync remains
responsible for personal installs.

## CLI and results

`--remind`, `--status` and `--reset` use local state without reading project
configuration or invoking update commands. Shell startup stays offline.
`--stale` scans and caches stale skills; `--prune` performs recoverable removal.
`--run` is the default, and `--help` lists the options.

| Exit | Meaning |
| --- | --- |
| 0 | All requested work completed. |
| 2 | A step skipped or sync returned partial success, with no failures. |
| 1 | At least one step failed; independent steps were still attempted. |

Normal runs stamp the day even when a step fails, so reminders stay silent until
tomorrow. Configuration errors and interrupted runs do not stamp the day. Retry
intentionally after fixing failures; `--reset` restores the startup reminder.
The existing XDG cache stamp and stale cache locations remain compatible.

## Review, deployment and verification

Use a topic worktree and review every affected deployed target, including the
launcher, TOML file and each Python module:

```sh
chezmoi --source /absolute/task/worktree diff -- /absolute/deployed/target
python3 -B -m unittest discover -s tests -p 'test_daily_update*.py' -v
```

After an approved local merge, deploy through `chezmoi-apply-unmodified` and
verify each target with `chezmoi diff -- /absolute/deployed/target`. Repository
synchronization and pushes require a separate request.

Tests use disposable homes, real Git/Just and local bare remotes, with contained
Codex, Claude, npm, GitHub and Homebrew substitutes. A real helper/chezmoi test
verifies deployment while preserving local edits and deletions. Configuration,
checkout guards, failure isolation, personal-source protection, reminders,
recoverable pruning and tool resolution are verified without live upgrades or
changes to installed skills.
