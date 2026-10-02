# Daily update and collection sync

`private_dot_config/my-scripts/bin/executable_daily-update` is the version-controlled
Bash source. Its managed target is `~/.config/my-scripts/bin/daily-update`.
Edit the source in a topic worktree. Review its rendered diff with:

```sh
chezmoi --source /absolute/path/to/task-worktree diff -- ~/.config/my-scripts/bin/daily-update
```

A local merge, publishing the dotfiles repository, and deploying that concrete
target are separate actions. This change does not deploy the script.

## Refresh policy

A normal `daily-update` preserves Codex/Claude upgrade behavior, then coordinates
these explicit personal checkouts:

1. `~/gh/my-skills` (`vimkim/my-skills`).
2. `~/gh/my-cubrid-skills` (`vimkim/my-cubrid-skills`).

For each independent Git checkout, inspect tracked and untracked work before
fetching its branch's configured remote. Require a tracking upstream and require
the current commit to be an ancestor of the freshly fetched upstream. Then
fast-forward with `git merge --ff-only` and invoke `just --justfile ./justfile sync`
inside that checkout. `git`, `just`, Bash, and each collection's documented sync
prerequisites must be installed. `jq` is required for lock-backed third-party work.

Dirty, ahead, diverged, detached, missing, nested non-checkout, and untracked-branch
checkouts are reported and skipped. Fetch or fast-forward failures report failure
and skip that collection's sync. Source files and commits are never discarded.

After the collections, the personal tool checkout `~/gh/my-git-utils`
(`vimkim/my-git-utils`) goes through the same checks, fast-forward, and
`just sync`, which reinstalls its commands with `uv tool install --editable`.
It is reported as `tool:my-git-utils` and holds no skills, so stale-skill
detection ignores it.
Fetch can update remote-tracking refs even when a diverged checkout is skipped.
An unrelated collection still proceeds after a failure or partial result. Set
`DAILY_UPDATE_COLLECTION_ORDER=cubrid-first` to process the same two collections in
reverse order.

`just sync` alone reconciles the current source contents with installed skills;
it does not refresh Git. The sync engine remains responsible for ownership,
conflicts, verification, migration, pruning and recovery. Missing peer evidence
prevents unsafe pruning there; daily-update does not infer ownership or duplicate
that reconciliation logic.

## Results and reminders

Per-collection output distinguishes `completed`, `partial/skipped (sync exit 2)`,
checkout skips, and `FAILED`. The normal run returns:

| Exit | Meaning |
| --- | --- |
| 0 | Every requested step completed; no skips or failures. |
| 2 | Some work skipped or partial, with no failed step. |
| 1 | At least one failed step; independent work was still attempted. |

As before, a run stamps the current day even when some steps fail. `--remind`
stays silent afterward; `--status`, `--reset`, and the existing tool resolution
and Homebrew handling retain their behavior. Re-run intentionally after fixing a
failure; use `--reset` to restore the startup reminder.

## Third-party maintenance boundary

The existing skill-update and stale-report/prune conveniences remain outside the
collection justfiles. They exclude both personal GitHub source identities (also
GitHub URL forms), the two configured local-source paths, and current personal
skill names, including third-party name collisions. Identity exclusion still
works when a personal checkout is missing or dirty. Skills absent from the
installer lock are outside legacy pruning, including dangling unowned links.

Third-party updates use `skills@1.7.0 update <eligible-name> ... --global --yes`.
An empty eligible set never becomes an unfiltered update. Malformed lock entries
or failed source inventory scans fail closed and report skipped maintenance.
The pinned CLI's positional filter limits installations to selected names; its
source-wide deletion prompt skips deletion with `--yes`. Existing third-party
upstream checks and recoverable `--prune` handling remain. Personal installs are
reconciled only by collection sync, so these legacy operations cannot override a
personal collection skip.

## Verification

```sh
bash -n private_dot_config/my-scripts/bin/executable_daily-update
shellcheck private_dot_config/my-scripts/bin/executable_daily-update
python3 -B -m unittest discover -s tests -p test_daily_update.py -v
```

The 13 public-entry-point tests invoke the Bash source using disposable homes,
Git checkouts and bare remotes. They use real Git/just/jq plus controlled failures;
Codex, Claude, npm, GitHub and Homebrew commands are contained substitutes, so
verification does not upgrade tools or touch installed skills. Configuration and
caches are confined to the disposable home. Coverage includes both processing
orders, refresh-before-sync, staged/untracked dirty work, ahead/diverged history,
fetch/fast-forward/sync failures, partial sync, missing/detached/untracked branches,
nested Git directories, failed first scans, protected personal GitHub/local
entries and name collisions, malformed locks, and reminder/status/reset behavior.

CLI contract inspected from the locally cached `skills@1.7.0` source:
`parseUpdateOptions` collects positional filters; `updateGlobalSkills` filters
before computing updates and invokes `add --skill <selected-name>` per update;
`promptDeletions` returns without removal when `options.yes` is set. No live
skills update was used as a test. Collection engine tests separately verify
ownership, pruning and real installer compatibility.
