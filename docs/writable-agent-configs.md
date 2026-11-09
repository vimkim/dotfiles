# Shared and local agent configuration

This repository is public. Claude Code and Codex settings are split into a
shared file that chezmoi manages and publishes, and local files that stay on
each machine because they hold company paths, internal tool rules, or
machine state.

## Where each setting lives

| Tool | Shared, managed by chezmoi | Local, never committed |
| --- | --- | --- |
| Claude | `~/.claude/settings.json` | `~/.claude/local-settings.json`, `~/.claude.json`, each repository's `.claude/settings.local.json` |
| Codex | `~/.codex/config.toml`, `~/.codex/hooks.json` | `~/.codex/local.config.toml`, `~/.codex/rules/default.rules` |

Chezmoi creates the two local files empty when they are missing
(`create_` sources) and never changes them afterwards.

Put company paths and internal tool rules only in local files: Claude
permission rules for internal CLIs, `autoMode` rules that name internal
services, `claudeMdExcludes` for company checkouts, and Codex project trust.

## Where the tools write

| Action | Claude writes to | Codex writes to |
| --- | --- | --- |
| Trust a folder | `~/.claude.json` | `local.config.toml` (the active profile) |
| Allow a command permanently | `.claude/settings.local.json` at the repository root | `~/.codex/rules/default.rules` |
| Approve a hook | Not required | `local.config.toml` (`[hooks.state]`) |
| `/model`, `/config`, and similar | `~/.claude/settings.json` (shared) | `local.config.toml` |

Codex writes trust, hook approvals, and UI preferences to the active user
config layer, which is the `--profile` file when one is selected
(`app-server/src/config_manager_service.rs` and `config/src/state.rs` in
Codex 0.167.0). Running plain `codex` without `--profile local` writes them to
the shared `config.toml` instead; the apply helper then skips that file until
the change is moved. A preference changed inside Codex therefore lands in the
local file; copy it to the shared file to publish it.

Claude combines `permissions.allow` from `settings.json` and the
`--settings` file (verified on 2026-11-09 with a rule in each file and a
control command that was denied).

## Launch the agents

The Bash, Zsh, and Nushell shortcuts select the local files:

- `ai`, `aip`, `cla`, `cyo`, and `cds` start Claude with `--settings ~/.claude/local-settings.json`.
- `cx` and `cxp` start Codex with `--profile local`.

For direct calls or automation, select them explicitly:

```bash
claude --settings "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/local-settings.json"
codex --profile local
codex exec --profile local "read prompt.md and execute"
```

Claude shortcuts use `CLAUDE_CONFIG_DIR` when that variable has a value.
Codex resolves its profile relative to `CODEX_HOME`, or `~/.codex` when unset.

## Publish a setting the tools changed

Claude saves `/config` and `/model` changes in the shared `settings.json`.
Review the change, then copy it into the source:

```bash
chezmoi diff -- ~/.claude/settings.json ~/.codex/config.toml
chezmoi re-add ~/.claude/settings.json ~/.codex/config.toml
git -C "$(chezmoi source-path)" diff
```

Before committing, move any company path, internal tool rule, or credential
from the diff to the local file. Until a change is re-added, the apply helper
skips the locally changed file, so deployment never discards it.

See the official [Claude settings](https://code.claude.com/docs/en/settings),
[Claude permissions](https://code.claude.com/docs/en/permissions), and
[Codex configuration](https://learn.chatgpt.com/docs/config-file/config-basic)
documentation, and [openai/codex#14601](https://github.com/openai/codex/issues/14601)
for the Codex request to separate project trust.

## Cancel a turn and close Codex

Codex shortcuts use its native keymap configuration in the shared
`~/.codex/config.toml`:

```toml
[tui.keymap.global]
leader = "ctrl-x"

[tui.keymap.chat]
interrupt_turn = "leader c"
```

Press Ctrl+X, then C to cancel a turn. Use `/exit` to close Codex.
Ctrl+C keeps Codex's built-in interrupt and exit behavior.
There is no custom bell or double-press confirmation, and Ctrl+X, Ctrl+C is not translated.
Inspect shortcuts with `/keymap`.

Codex runs directly in the pane's terminal, so herdr and Ovis can identify its process.
New Bash, Zsh, and Nushell sessions have no `codex` alias.
The `codex-safe` command remains as a compatibility launcher for existing shell aliases:
it immediately replaces itself with `codex`, forwarding arguments without filtering keys.

Claude Code keeps its existing keybindings: Ctrl+X, then Ctrl+C cancels a turn.
See the official [Codex keymap configuration](https://learn.chatgpt.com/docs/config-file/config-basic#tui-keymap)
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

## Other managed files

| Source | Destination | Purpose |
| --- | --- | --- |
| `dot_claude/keybindings.json` | `~/.claude/keybindings.json` | Claude shortcuts, including protected chat cancellation |
| `private_dot_config/my-scripts/bin/executable_codex-safe` | `~/.config/my-scripts/bin/codex-safe` | Compatibility command for existing `codex-safe` aliases |
| `dot_gitconfig` | `~/.gitconfig` | Shared Git settings and the local include |
| `create_private_dot_gitconfig.local` | `~/.gitconfig.local` | Initial Git exceptions, created only if missing |
| `private_dot_config/lazygit/config.yml` | `~/.config/lazygit/config.yml` | Current lazygit schema |

## Migrate a machine to the shared and local split

The former `~/.claude/dotfiles-settings.json` and `~/.codex/dotfiles.config.toml`
are no longer managed. On each machine, before deploying:

1. Back up `~/.claude/settings.json`, `~/.codex/config.toml`, and both former files.
2. Write `~/.claude/local-settings.json` with the company entries from
   `settings.json` and the former Claude file, and `~/.codex/local.config.toml`
   with every `[projects.*]` table, `[hooks.state]`, and UI state from `config.toml`.
3. Make `settings.json` and `config.toml` match their sources, so the helper
   applies nothing over them, then run `chezmoi-apply-unmodified`.
4. Confirm `chezmoi diff` is empty for both shared files, start each tool with
   its shortcut, and approve the new work-tracker hook in Codex with `/hooks`.
5. Delete the former files after both tools start cleanly.
