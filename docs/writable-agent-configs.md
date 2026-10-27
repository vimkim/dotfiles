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
| `private_dot_config/my-scripts/bin/executable_codex-safe` | `~/.config/my-scripts/bin/codex-safe` | Interactive Codex shortcut protection |
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
- `codex` selects `codex-safe` through a shell alias. `cx` and `cxp` inherit that alias.

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
The interactive `codex` alias also sets the protected cancellation keymap.
Use direct `codex` when selecting another profile.
Managed defaults override matching local preferences when the shortcut selects them.
Edit the managed source to change those defaults.

See the official [Claude settings documentation](https://code.claude.com/docs/en/settings)
and [Codex configuration documentation](https://learn.chatgpt.com/docs/config-file/config-basic).

## Cancel a turn and close Codex

Open a new Bash, Zsh, or Nushell session after deployment.
The `codex`, `cx`, and `cxp` aliases then use `codex-safe`.
Existing Codex processes keep their previous keyboard behavior.

| Key | Codex through the alias | Claude Code |
| --- | --- | --- |
| Escape | Leaves the current turn running. Still closes menus. | Leaves the current turn running. Still closes menus. |
| Ctrl+X, then Ctrl+C | Cancels the current turn. Keeps the session open. | Cancels the current turn. Keeps the session open. |
| Ctrl+C once | Rings the terminal bell. Keeps the turn and session running. | Uses Claude's built-in interrupt behavior. |
| Ctrl+C twice within one second | Cancels active work and closes the Codex terminal session. | Uses Claude's built-in behavior. |

Codex 0.164.0 reserves Ctrl+C for interrupt and quit handling.
It rejects that key inside a custom chord.
The wrapper translates Ctrl+X, Ctrl+C to the native Ctrl+X, C shortcut.
The native shortcut also works. Codex displays it in shortcut hints.
The wrapper sets this keymap for interactive launches, including `resume` and `fork`.
An explicit conflicting `-c tui.keymap...` override can change that behavior.

The wrapper uses a pseudo-terminal and the Python standard library.
It preserves terminal dimensions, exit status, bracketed paste, and keyboard protocol messages.
It forwards external termination signals and restores terminal settings when Codex exits.
The shortcut protection also applies inside external editors opened from that session.

Commands such as `codex exec`, `codex review`, and `codex --help` bypass the wrapper's input handling.
Piped input or output also bypasses input handling.
These paths retain their original arguments and exit status.
Use `command codex` in Bash or Zsh, or `^codex` in Nushell, to bypass the alias explicitly.
The original binary retains its native Ctrl+C behavior.

Claude reloads its keybindings file automatically.
Other bindings in the existing file remain present.
Its Ctrl+C key remains reserved by Claude.
See the official [Codex keymap reference](https://learn.chatgpt.com/docs/developer-commands#remap-tui-shortcuts-with-keymap)
and [Claude keybindings reference](https://code.claude.com/docs/en/keybindings).

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
