# Daily update and collection sync

`private_dot_config/my-scripts/bin/executable_daily-update` is the version-controlled
Bash source. Its managed target is `~/.config/my-scripts/bin/daily-update`.
Edit the source in a topic worktree. Review its rendered diff with:

```sh
chezmoi --source /absolute/path/to/task-worktree diff -- ~/.config/my-scripts/bin/daily-update
```

After review and an approved local merge, the repository workflow deploys with
`chezmoi-apply-unmodified`. Publishing the dotfiles repository requires a separate
request.

## Dotfiles refresh and deployment

A normal `daily-update` starts with the configured dotfiles source checkout,
resolved with `chezmoi source-path`, regardless of the calling directory. It
requires an independent Git checkout with no tracked or untracked changes, on
`main` tracking `origin/main`, with `origin` identifying `vimkim/dotfiles` through
an HTTPS or GitHub SSH URL. Missing tools or source checkouts, other branches,
detached HEAD, missing upstreams and unexpected origins are reported as skips.

After those checks, it runs:

```sh
git -C "$source" fetch -- origin refs/heads/main:refs/remotes/origin/main
git -C "$source" merge-base --is-ancestor HEAD origin/main
git -C "$source" merge --ff-only -- origin/main
chezmoi-apply-unmodified --source "$source"
```

Each command depends on the previous command succeeding. Fetch requests `main`
explicitly so a deleted remote branch fails instead of leaving an old
`origin/main` to authorize deployment. The ancestor check skips ahead or diverged
checkouts; `--ff-only` alone can succeed when local commits are ahead. Local
commits must be published before a subsequent daily run will deploy them.

The helper runs even when the source is already current, so a retry can finish
an earlier deployment. It considers all managed files and symlinks, preserves
locally edited/deleted targets and existing targets without last-write history,
and excludes run scripts and directory removals. Its skip messages remain visible
and make the daily run partial (exit 2), although the helper itself returns
success for skips. A helper error, failed source lookup, failed Git inspection,
fetch failure or fast-forward failure counts as failed work (exit 1). Independent
tool and collection updates still proceed after any dotfiles result.

This treats `origin/main` as a trusted deployment source. Applying a new version
of `daily-update` updates its file; the current invocation continues with the
functions it already loaded, and the next invocation uses the new version.
`--remind`, `--status`, `--stale`, `--prune`, `--reset` and `--help` do not run the
dotfiles step.

## Collection and tool refresh

After dotfiles, `daily-update` preserves Codex/Claude upgrade behavior, then
coordinates these explicit personal checkouts:

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
detection ignores it. `~/gh/html-serve` (`vimkim/html-serve`) is refreshed as
`tool:html-serve` using the same editable installation pattern. Like
`herdr-next-to-current`, it requires a primary main checkout tracking origin/main
and the expected origin; a task checkout is preserved and skipped. A locally
created repository without a published upstream is skipped until publication.
Fetch can update remote-tracking refs even when a diverged checkout is skipped.
An unrelated collection still proceeds after a failure or partial result. Set
`DAILY_UPDATE_COLLECTION_ORDER=cubrid-first` to process the same two collections in
reverse order.

`~/gh/dirpick` (`vimkim/dirpick`) runs after these tools as `tool:dirpick`.
It requires a clean, independent primary checkout on `main` tracking
`origin/main`, with the expected GitHub origin. Symlinks and linked worktrees
are skipped. Its fetch requests remote `main` explicitly, so deletion cannot
leave a stale reference eligible for installation. After the same ancestor
check and fast-forward, `~/.config/my-scripts/bin/install-dirpick` installs
the locked Cargo package into `~/.local/bin`. Dirpick needs Rust/Cargo, without
a `justfile`. An unchanged checkout still reinstalls, allowing a failed build
to be retried. Missing installers and failed builds report failure while
independent steps continue. See [Dirpick setup](dirpick.md) for bootstrap and
Nushell integration.

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
python3 -B -m unittest discover -s tests -p test_install_dirpick.py -v
```

The public-entry-point tests invoke the Bash source using disposable homes,
Git checkouts and bare remotes. They use real Git/just/jq plus controlled failures;
Codex, Claude, npm, GitHub and Homebrew commands are contained substitutes, so
verification does not upgrade tools or touch installed skills. A real chezmoi
and helper integration test verifies deployment to a disposable destination;
other tests substitute the helper to exercise orchestration failures.
Configuration and caches are confined to the disposable home. Dotfiles coverage
includes refresh/apply before upgrades, configured source paths containing spaces,
unchanged-source retries, branch/origin/cleanliness guards, unpublished local
commits, deleted remote `main`, failed Git steps, helper failures and partial
deployment, and preserved local target edits/deletions. Coverage also includes both
processing orders, refresh-before-sync, staged/untracked dirty work, ahead/diverged history,
fetch/fast-forward/sync failures, partial sync, missing/detached/untracked branches,
nested Git directories, failed first scans, protected personal GitHub/local
entries and name collisions, malformed locks, and reminder/status/reset behavior.

CLI contract inspected from the locally cached `skills@1.7.0` source:
`parseUpdateOptions` collects positional filters; `updateGlobalSkills` filters
before computing updates and invokes `add --skill <selected-name>` per update;
`promptDeletions` returns without removal when `options.yes` is set. No live
skills update was used as a test. Collection engine tests separately verify
ownership, pruning and real installer compatibility.
