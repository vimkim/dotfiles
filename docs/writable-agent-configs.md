# Managed defaults and writable application settings

Claude Code and Codex write preferences and local state into their user configuration files.
Chezmoi preserves those writes by leaving these files unmanaged:

- `~/.claude/settings.json`
- `~/.codex/config.toml`

Chezmoi creates `~/.gitconfig.local` only when the file is missing.
Its `create_` source leaves existing contents unchanged.
Future edits belong in this local file.

Removing a source entry leaves its existing destination in place.
The migration does not add these files to `.chezmoiremove`.
Claude keeps its Herdr hook, instruction exclusions, and plugin configuration.
Codex keeps project trust, hook approvals, plugin choices, and UI state.

## Managed files

| Source | Destination | Purpose |
| --- | --- | --- |
| `dot_claude/private_dotfiles-settings.json` | `~/.claude/dotfiles-settings.json` | Shared Claude defaults, including `opus` |
| `dot_codex/private_dotfiles.config.toml` | `~/.codex/dotfiles.config.toml` | Shared Codex defaults, including `gpt-6.1-sol` and `xhigh` |
| `dot_claude/keybindings.json` | `~/.claude/keybindings.json` | Claude shortcuts, including protected chat cancellation |
| `private_dot_config/my-scripts/bin/executable_codex-safe` | `~/.config/my-scripts/bin/codex-safe` | Compatibility command for existing `codex-safe` aliases |
| `dot_gitconfig` | `~/.gitconfig` | Shared Git settings and the local include |
| `create_private_dot_gitconfig.local` | `~/.gitconfig.local` | Initial Git exceptions, created only if missing |
| `private_dot_config/lazygit/config.yml` | `~/.config/lazygit/config.yml` | Current lazygit schema |

Claude and Codex default files contain preferences that the repository controls.
They exclude application-maintained plugin choices and approval records.
The Codex profile enables the existing hooks and goals features.

## Launch the agents

The Bash, Zsh, and Nushell shortcuts select these defaults:

- `ai` and `aip` load Claude's defaults with `--settings`.
- Nushell's `cla`, `cyo`, and `cds` also load Claude's defaults.
- `cx` and `cxp` select the Codex `dotfiles` profile.
- `codex` launches the native CLI directly; `cx` and `cxp` select its `dotfiles` profile.

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

## Cancel a turn and close Codex

Codex shortcuts use its native keymap configuration in `~/.codex/dotfiles.config.toml`.
Launch with `cx`, `cxp`, or `codex --profile dotfiles` to select those settings:

```toml
[tui.keymap.global]
leader = "ctrl-x"

[tui.keymap.chat]
interrupt_turn = "leader c"
```

Press Ctrl+X, then C to cancel a turn. Use `/exit` to close Codex.
Ctrl+C keeps Codex's built-in interrupt and exit behavior.
There is no custom bell or double-press confirmation, and Ctrl+X, Ctrl+C is not translated.
Plain `codex` uses its local user settings. Inspect shortcuts with `/keymap`.

Codex runs directly in the pane's terminal, so herdr and Ovis can identify its process.
The previous Python relay created a separate pseudo-terminal that hid Codex from herdr's
foreground process list. New Bash, Zsh, and Nushell sessions have no `codex` alias.
The `codex-safe` command remains as a compatibility launcher for existing shell aliases:
it immediately replaces itself with `codex`, forwarding arguments without filtering keys.
Already running relay processes keep their behavior until the user exits and resumes Codex.

Claude Code keeps its existing keybindings: Ctrl+X, then Ctrl+C cancels a turn.
It reloads its keybindings file automatically.
See the official [Codex keymap configuration](https://learn.chatgpt.com/docs/config-file/config-basic#tui-keymap),
[Codex commands](https://learn.chatgpt.com/docs/developer-commands), and
[Claude keybindings reference](https://code.claude.com/docs/en/keybindings).

## Keep Git exceptions local

The managed `.gitconfig` includes `~/.gitconfig.local`.
Git treats that include as user configuration.
The initial local file contains `/home/dev/cubrid-dev2-server` as a `safe.directory` exception.
An existing local file keeps its contents.
Report any missing exception instead of overwriting that file.

Write future machine-specific settings to the local file:

```bash
git config --file "$HOME/.gitconfig.local" --add safe.directory /absolute/checkout
git config --global --includes --show-origin --get-all safe.directory
```

`git config --global` writes to the managed `.gitconfig` unless you select another file.
Use `--file` for local edits.
See [Git includes](https://git-scm.com/docs/git-config#_includes).

## Deploy the configuration split

The helper does not accept local edits automatically when they match the source.
Keep skipped targets protected throughout this migration.

1. Inspect existing settings and Git exceptions before deployment.
   Preserve all local contents.
2. Obtain approval to merge the complete branch.
   Do not deploy intermediate commits from this branch.
3. Run the helper once for all managed files and symlinks in the configured source checkout:

   ```bash
   bash <absolute-merged-checkout>/private_dot_config/my-scripts/bin/executable_chezmoi-apply-unmodified
   ```

4. Check the managed targets with `chezmoi diff`.
   Check that both unmanaged agent files retain their contents.
   Check that an existing `~/.gitconfig.local` retains its contents.
   Check the local and effective Git exceptions:

   ```bash
   git config --file "$HOME/.gitconfig.local" --get-all safe.directory
   git config --global --includes --show-origin --get-all safe.directory
   ```

5. Preserve and report every helper skip and any missing Git exception.
   A skipped `.gitconfig` leaves the include migration incomplete.
   Do not reset chezmoi state or force an overwrite to complete the migration.
6. Complete the task's Git cleanup after the required deployment checks.

See [helper behavior and checks](chezmoi-apply-unmodified.md).
