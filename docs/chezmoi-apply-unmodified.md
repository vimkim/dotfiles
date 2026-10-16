# Apply dotfiles while preserving local changes

`chezmoi-apply-unmodified` lives in `~/.config/my-scripts/bin`, which is already
on PATH. It applies files and symlinks that remain unchanged since chezmoi's last
write. It reports a local edit or deletion as
`Skipped locally changed target: ...`. Skips return success. The helper also
preserves existing destinations without last-write history and reports a separate
skip message. It applies previously managed destinations that already match the
source to refresh last-write history. This records a reviewed local edit adopted
into the source. Later source updates can then deploy normally.

```bash
chezmoi-apply-unmodified
chezmoi-apply-unmodified --source /absolute/source/checkout
chezmoi-apply-unmodified --source /absolute/source/checkout -- /absolute/target/file
```

The first two forms consider all managed files and symlinks. The third selects
one file. The helper defaults to chezmoi's configured source checkout, regardless
of the current directory. Use `--source` only to select a different checkout.
`--config FILE` selects another chezmoi configuration when needed.

The helper completes `chezmoi status` and a NUL-delimited `chezmoi managed`
inventory before applying anything. It reads the first status column to identify
local changes and checks for recorded last-write history before applying an
existing destination. The inventory includes matching files omitted from status.
It then invokes chezmoi separately for each remaining target and creates missing
parent directories. Each apply checks for conflicts again. An edit made after
the scan can still cause an error that preserves the destination. A failed scan
or apply returns nonzero. The helper does not support filenames containing
newlines. It rejects malformed status output and unsupported managed paths before
applying any target. Each apply includes files, symlinks, and their parent
directories only. The helper preserves existing parent directory permissions.

Run scripts and directory removals require separate handling. A successful run
processes all selected files, including expected skips. Some destinations may
still differ from their sources.

For applications that write their own configuration, use separate managed
defaults when supported. See [agent defaults and the Git migration](writable-agent-configs.md).

## Agent deployment

Follow the repository workflow in [AGENTS.md](../AGENTS.md). After an approved
merge into the configured source checkout, run `chezmoi-apply-unmodified` once.
Preserve and report skipped targets and any remaining differences. A successful
helper exit can include skips.

If the helper is not on PATH, run its source directly:

```bash
bash <absolute-merged-checkout>/private_dot_config/my-scripts/bin/executable_chezmoi-apply-unmodified
```

## Verification

```bash
bash -n private_dot_config/my-scripts/bin/executable_chezmoi-apply-unmodified
shellcheck private_dot_config/my-scripts/bin/executable_chezmoi-apply-unmodified
python3 -m unittest discover -s tests -p test_chezmoi_apply_unmodified.py -v
```

The integration tests use real chezmoi with disposable source, destination,
configuration, cache, and state files. They cover normal updates, local edits,
deletions, pre-existing files, nested paths, symlinks, and explicit targets.
They also cover accepted baselines, concurrent edits, script exclusion, empty
selections, and failures before deployment.
