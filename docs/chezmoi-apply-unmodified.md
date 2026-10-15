# Apply dotfiles while preserving local changes

`chezmoi-apply-unmodified` lives in `~/.config/my-scripts/bin`, which is already
on PATH. It applies files and symlinks whose destinations have not changed since
chezmoi last wrote them. A local edit or deletion is reported as
`Skipped locally changed target: ...` and returns success. An existing destination
without last-write history is also preserved, with a separate skip message.

```bash
chezmoi-apply-unmodified
chezmoi-apply-unmodified --source /absolute/source/checkout -- /absolute/target/file
```

The first form considers all managed files and symlinks. Repository agents use
the second form separately for each affected file, with the merged checkout as
the source. `--config FILE` selects another chezmoi configuration when needed.

The helper completes `chezmoi status` before applying anything. It reads the
first status column to identify local changes and checks for recorded last-write
history before replacing an existing destination. It then invokes chezmoi
separately for each remaining target. Missing parent directories are created.
Each apply checks for conflicts again; an edit made after the scan can still
cause an error, preserving the destination. A failed status scan or apply
returns nonzero. Filenames containing newlines are unsupported; malformed
status output is rejected before any target is applied.

Run scripts and directory removals require separate handling. The helper's
success means all selected files were processed, including expected skips;
it does not mean the destination now matches every source file.

## Proposed project guidance

Keep root `AGENTS.md` and `CLAUDE.md` identical when adopting this proposal.
Replace workflow steps 4–6 with:

> 4. After every approved merge, complete any explicitly requested push to `main`
>    before deployment. If that push fails, report the failure before proceeding.
>    Process each affected dotfile with
>    `chezmoi-apply-unmodified --source <absolute-merged-checkout> -- <absolute-target>`,
>    using one absolute file target per invocation. Merge approval authorizes
>    this deployment. If the helper is not on PATH, invoke the same script with
>    `bash <absolute-merged-checkout>/private_dot_config/my-scripts/bin/executable_chezmoi-apply-unmodified`
>    and the same arguments to install the helper first.
> 5. Verify each processed target with
>    `chezmoi --source <absolute-merged-checkout> diff -- <absolute-target>`.
>    An empty diff confirms deployment. For a target explicitly reported as
>    skipped, preserve the local file and report its remaining differences;
>    this is an expected outcome. Report other command failures as blockers.
> 6. Complete Git cleanup as specified in `dot_codex/AGENTS.md`. Report the
>    checkout, branch, commit, checks, applied targets, skipped targets, and
>    remaining dirt or blockers. Completion requires every affected file to be
>    applied and verified, or explicitly skipped and reported, plus Git cleanup.

Keep the existing restriction to individual file targets. Add this rule beside it:

> Use `chezmoi-apply-unmodified` for every file deployment. Review diffs with
> `chezmoi diff`; preserve and report expected skips when differences remain.

Changing only the apply command would leave the current completion rule
requiring every skipped conflict to be resolved. The verification and completion
rules above make preserving those local changes an expected result.

## Verification

```bash
bash -n private_dot_config/my-scripts/bin/executable_chezmoi-apply-unmodified
shellcheck private_dot_config/my-scripts/bin/executable_chezmoi-apply-unmodified
python3 -m unittest discover -s tests -p test_chezmoi_apply_unmodified.py -v
```

The integration tests use real chezmoi with disposable source, destination,
configuration, cache, and state files. They cover normal updates, local edits
and deletions, pre-existing files, nested paths, symlinks, explicit targets,
script exclusion, empty selections, and failures before deployment.
