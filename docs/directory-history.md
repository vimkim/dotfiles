# Shared directory history

`dir-history` owns directory history for Bash, Zsh, and Nushell. It is a Python 3
command using the standard `sqlite3` module. Shell adapters record visits and
perform `cd` in the calling shell. Bash and Zsh history operations do not require
Nushell.

## Commands

| Command | Behavior |
| --- | --- |
| `ch` | Pick a visited directory with fzf, enter it, and list its contents. |
| `ch --forget`, `chf` | Pick one or more paths to remove from history only. |
| `ch --delete`, `chd` | Pick directories, confirm, then move them to trash. |
| `ch --prune`, `chp` | Remove missing directories from history. |
| `vh` | View history; Nushell returns a list, Bash/Zsh print JSON. |

The shared command also exposes:

```sh
dir-history record -- "$PWD"
dir-history pick --json
dir-history pick --null
dir-history list --json
dir-history list --null
dir-history forget -- "/absolute/path"
dir-history prune
dir-history migrate
```

Paths passed to `record` and `forget` must be absolute. Recording requires an
existing directory. Logical paths retain symlinks and their exact spelling.
The picker escapes tabs, newlines, and terminal controls for display and returns
the original path through a stable selection index. JSON and NUL-delimited output
preserve whitespace and newlines. Cancelling a picker leaves the current directory
and history unchanged.

fzf is required for selection. Trash operations use `gio trash` or `trash-put`.
Root, home, the current directory, and its ancestors are protected, including
equivalent paths through symlinks. Entries are removed only after successful
trash operations; failed operations remain in history. Confirmation and trash
operations run outside database transactions.

## Recording and storage

The database is
`${XDG_STATE_HOME:-$HOME/.local/state}/dir-history/history.sqlite3`. A relative
`XDG_STATE_HOME` is ignored. Newly created databases have mode `0600`.

Bash records the current directory before each prompt when it has changed;
intermediate changes inside a single command are not recorded. Zsh uses directory
change hooks and records the initial directory before its first prompt. Nushell
uses its PWD environment-change hook. Reloading adapters preserves unrelated hooks
and avoids duplicate history hooks. Hook recording preserves the previous command's
exit status. A failed write is reported and can be retried on a later prompt or
directory change.

History contains at most 150 unique paths, ordered by their latest recorded visit.
Visit ordering uses a database counter computed under the write lock rather than
wall-clock timestamps. A visit and retention cleanup commit in one transaction.
Concurrent shells cannot overwrite an entire history snapshot.

SQLite WAL allows readers during a write and serializes writers. Lock waits are
bounded to 500 ms per SQLite operation; initialization also retries transient WAL
setup contention for a bounded interval. A persistently busy database produces an
error, rather than silently dropping or resetting history. A Bash/Zsh hook that
cannot record a visit leaves its last-recorded marker unchanged so it can retry.
No transaction remains open while fzf or a confirmation prompt waits for input.
Pruning removes only entries whose visit order has not changed since the scan.

Keep this database on local storage on each host. WAL is intended for processes
on the same host, and its `-wal` and `-shm` files belong to SQLite. Do not put the
live database in chezmoi or copy/sync it while it is open. See
[SQLite WAL](https://www.sqlite.org/wal.html) and the
[XDG state-directory specification](https://specifications.freedesktop.org/basedir/latest/).

## Migration and existing sessions

On first initialization, the command imports
`~/.local/share/nu/dirlog.json` under the same transaction that creates its schema.
It preserves newest-first order, deduplicates paths, ignores invalid entries,
and retains up to 150. The original JSON file remains byte-for-byte unchanged as
a backup. The database records that initialization is complete; later starts do
not reimport old entries or resurrect forgotten paths. `dir-history migrate`
performs this initialization explicitly or reports the completed import.

Malformed JSON, unreadable files, damaged databases, and unknown schema versions
produce errors. None is treated as empty history. Repair the reported file and
retry; the command does not replace it automatically.

After targeted chezmoi deployment, initialize migration with:

```sh
dir-history migrate
```

Reload each existing Bash/Zsh session:

```sh
source ~/.config/my-scripts/shell/productivity.sh
```

Reload each existing Nushell session:

```nu
source ~/.config/nushell/dir-history.nu
```

The Nushell adapter replaces its old JSON-writing hook while preserving other
PWD hooks. Until reloaded, an old Nushell session continues writing JSON; visits
written there after import do not enter SQLite. Reload or close old Nushell
sessions at cutover. New sessions load the SQLite adapter automatically.

The deprecated `directory-history.nu` executable is a compatibility launcher for
already-open Bash/Zsh sessions. It forwards their old arguments to `dir-history`
and writes only SQLite. It can be removed after those sessions have been reloaded.

## Verification

```sh
python3 -B -m unittest discover -s tests -p test_dir_history.py
python3 -B -m unittest discover -s tests -p test_shell_productivity.py
```

These checks cover migration and retention, 24 simultaneous cold-start writers,
lock contention and recovery, database errors, exact paths through fzf and shell
adapters, cancellation, trash protection/failure, legacy launcher compatibility,
and replacement of Nushell's old hook.
