# Managed defaults and writable application settings

Claude Code and Codex write preferences and local state into their user configuration files.
Chezmoi preserves those writes by leaving these files unmanaged:

- `~/.claude/settings.json`
- `~/.codex/config.toml`
- `~/.gitconfig.local`

Removing a source entry leaves its existing destination in place.
The migration does not add these files to `.chezmoiremove`.
Claude keeps its Herdr hook, instruction exclusions, and plugin configuration.
Codex keeps project trust, hook approvals, plugin choices, and UI state.

## Managed files

| Source | Destination | Purpose |
| --- | --- | --- |
| `dot_claude/private_dotfiles-settings.json` | `~/.claude/dotfiles-settings.json` | Shared Claude defaults, including `opus` |
| `dot_codex/private_dotfiles.config.toml` | `~/.codex/dotfiles.config.toml` | Shared Codex defaults, including `gpt-6.1-sol` and `xhigh` |
| `dot_gitconfig` | `~/.gitconfig` | Shared Git settings and the local include |
| `private_dot_config/lazygit/config.yml` | `~/.config/lazygit/config.yml` | Current lazygit schema |

Claude and Codex default files contain preferences that the repository controls.
They exclude application-maintained plugin choices and approval records.
The Codex profile enables the existing hooks and goals features.

## Launch the agents

The Bash, Zsh, and Nushell shortcuts select these defaults:

- `ai` and `aip` load Claude's defaults with `--settings`.
- Nushell's `cla`, `cyo`, and `cds` also load Claude's defaults.
- `cx` and `cxp` select the Codex `dotfiles` profile.

Claude shortcuts use `CLAUDE_CONFIG_DIR` when that variable has a value.
Otherwise, they use `~/.claude`.
Provision the defaults file in that directory when using a custom configuration directory.
Codex resolves its profile relative to `CODEX_HOME`, or `~/.codex` when unset.

For direct calls or automation, select the defaults explicitly:

```bash
claude --settings "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/dotfiles-settings.json"
codex --profile dotfiles
codex exec --profile dotfiles "read prompt.md and execute"
```

Direct `claude` and `codex` calls continue to use their local user settings.
Use direct `codex` when selecting another profile.
Managed defaults override matching local preferences when the shortcut selects them.
Edit the managed source to change those defaults.

See the official [Claude settings documentation](https://code.claude.com/docs/en/settings)
and [Codex configuration documentation](https://learn.chatgpt.com/docs/config-file/config-basic).

## Keep Git exceptions local

The managed `.gitconfig` includes `~/.gitconfig.local`.
Git treats that include as user configuration.
The migration preserves `/home/dev/cubrid-dev2-server` as a `safe.directory` exception.

Write future machine-specific settings to the local file:

```bash
git config --file "$HOME/.gitconfig.local" --add safe.directory /absolute/checkout
git config --global --includes --show-origin --get-all safe.directory
```

`git config --global` writes to the managed `.gitconfig` unless you select another file.
Use `--file` for local edits.
See [Git includes](https://git-scm.com/docs/git-config#_includes).

## Deploy the migration in two stages

Obtain approval for both local merge checkpoints before deployment.
Keep both deployment checkpoints when rebasing or squashing the commits.
Use the configured source checkout for each helper invocation.

1. Merge the first commit, which adopts the reviewed Git and lazygit contents.
   This commit also fixes baseline recording and creates a Git local seed.
2. Run the merged helper once for all managed files and symlinks.
   Invoke its source directly so this run uses the fixed helper:

   ```bash
   bash <absolute-merged-checkout>/private_dot_config/my-scripts/bin/executable_chezmoi-apply-unmodified
   ```

3. Check the Git and lazygit diffs.
   Check that `.gitconfig.local` preserves the required exception:

   ```bash
   chezmoi diff -- "$HOME/.gitconfig" "$HOME/.config/lazygit/config.yml" "$HOME/.gitconfig.local"
   git config --file "$HOME/.gitconfig.local" --get-all safe.directory
   ```

4. Stop before stage two if the helper skips either reviewed target or the required exception is missing.
   Preserve any new local changes for review.
5. Merge the second commit, which separates agent defaults and adds Git's local include.
   This commit removes the Git local seed from the source.
   The existing `.gitconfig.local` remains on disk and becomes unmanaged.
   The commit also changes lazygit's `colorArgs` key to `colorArg`.
6. Run the helper once for all managed files and symlinks.
7. Check the managed targets with `chezmoi diff`.
   Check that the three unmanaged files retain their contents.
   Check the effective Git exception with `--includes`.
   Preserve and report any helper skips.
8. Complete the task's Git cleanup.

The first helper run records matching Git and lazygit files as accepted baselines.
This permits the second run to deploy their source updates without forced overwrites.
The helper still preserves new local changes made between the two stages.

See [helper behavior and checks](chezmoi-apply-unmodified.md).
