# Apply dotfiles while preserving local changes

`chezmoi-apply-unmodified` lives in `~/.config/my-scripts/bin`, which is already
on PATH. It applies files and symlinks whose destinations have not changed since
chezmoi last wrote them. A local edit or deletion is reported as
`Skipped locally changed target: ...` and returns success. An existing destination
without last-write history is also preserved, with a separate skip message.
Previously managed destinations that already match the source are also applied
to refresh last-write history. This records a reviewed local edit that has been
adopted into the source, so a later source update can be deployed normally.

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
It then invokes chezmoi separately for each remaining target. Missing parent
directories are created.
Each apply checks for conflicts again; an edit made after the scan can still
cause an error, preserving the destination. A failed status scan or apply
returns nonzero. Filenames containing newlines are unsupported; malformed
status output and unsupported managed paths are rejected before any target is
applied. Each apply includes files, symlinks, and their parent directories only.

Run scripts and directory removals require separate handling. The helper's
success means all selected files were processed, including expected skips;
it does not mean the destination now matches every source file.

## Agent deployment

Follow the repository workflow in [AGENTS.md](../AGENTS.md). After an approved
merge into the configured source checkout, run `chezmoi-apply-unmodified` once.
Preserve and report skipped targets and any remaining differences; a successful
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
configuration, cache, and state files. They cover normal updates, local edits
and deletions, pre-existing files, nested paths, symlinks, explicit targets,
accepted file and symlink baselines, script exclusion, empty selections, and
failures before deployment.
