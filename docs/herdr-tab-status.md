# Herdr tab agent indicators

The managed `herdr-tab-status` updater adds agent state to tab names and publishes
a tab inventory under every workspace in the expanded sidebar. It uses Herdr's
existing socket API and runs with Python's standard library on Linux.

Example tab labels:

```text
1 [▶ Codex]     review [! Claude]     logs [— shell]
```

Example workspace entry:

```text
● dotfiles · working
main · * ↑2
4 tabs · 6 panes · 3 agents
1 ▶ Codex · 2 ! Claude · 3 ✓ Codex
4 — shell
```

## State and naming

| Marker | Meaning |
| --- | --- |
| `▶` | Agent working |
| `!` | Agent blocked, awaiting approval or an answer |
| `✓` | Agent done, with an unseen response |
| `○` | Agent idle |
| `?` | Agent detected, but its state is unknown |
| `—` | No detected agent; an ordinary terminal |

The updater reads `session.snapshot`: agent entries determine which tabs contain
agents, and each tab's native `agent_status` supplies the aggregate state. Multiple
agents appear as, for example, `review [! Claude+Codex ×2]`. Shells, editors, and
servers without a detected agent get the ordinary-terminal marker.

The server's `done`/`idle` distinction uses its seen state. Each attached client
can track viewed responses independently, so its native Done badge can differ
from the updater. These markers are text decorations; setting sidebar symbol
colors does not color the decorations themselves.

Original tab names remain before the status suffix. Tab order and shortcut
bindings are unchanged. Sidebar numbers follow the current shortcut positions;
a numeric tab *name* remains its original name after reordering. User renames
observed during updates become the new original name, including edits that keep
the current managed suffix. The API does not offer conditional renames, so a
manual rename made between a snapshot and its rename request can race the updater.

Sidebar summaries normally include agent types. If there are too many for the
13 available summary rows, they switch to compact markers such as `1▶ 2! 3—`.
If those also exceed the rows, the final line points to the tab bar for the rest.
Missing summary rows disappear. The agent panel also shows state, workspace,
tab/pane names, and the terminal activity title.

## Managed files

| Chezmoi source | Deployed target |
| --- | --- |
| `private_dot_local/bin/executable_herdr-tab-status` | `~/.local/bin/herdr-tab-status` |
| `private_dot_local/bin/executable_herdr-shell` | `~/.local/bin/herdr-shell` |
| `private_dot_config/herdr/config.toml` | `~/.config/herdr/config.toml` |

Verify each target with `chezmoi --source <absolute-task-worktree> diff -- <target>`.
After the reviewed sources are merged, deploy the three verified targets
separately:

```sh
chezmoi apply -- "$HOME/.local/bin/herdr-tab-status"
chezmoi apply -- "$HOME/.local/bin/herdr-shell"
chezmoi apply -- "$HOME/.config/herdr/config.toml"
```

Use Herdr's reload-config action (`Ctrl+a`, then `Shift+r` with these bindings)
to reload the client's sidebar layout. Run the following inside a Herdr pane to
start the updater for existing tabs:

```sh
herdr-tab-status preview  # read-only planned labels and sidebar metadata
herdr-tab-status start
```

New panes launched by `herdr-shell` start it automatically before Nushell, zsh,
or bash. Startup returns immediately; a socket-specific file lock ensures one
worker per session. It uses the caller's `HERDR_SOCKET_PATH`, never the focused
workspace or another saved machine. It polls every two seconds and sends tab
renames only when labels change. Sidebar metadata refreshes on change and every
20 seconds, with a 60-second expiration.

## Stop and recovery

```sh
herdr-tab-status stop
```

For a running worker, this requests a graceful stop on its next loop. Stopping
restores names it still owns and clears only its own `user:tab-status` metadata.
Other reporters, including Git dirty status, keep their values. It also works
after a worker exits: the journal supplies the original names.

Private journals, locks, and error logs live under
`${XDG_CACHE_HOME:-$HOME/.cache}/herdr-tab-status/<socket-hash>/`. Write-ahead
journaling retains original names when a rename succeeds but its API reply is
lost. Keep the journal until decorated tabs have been restored. After a server
restart or abrupt worker exit, `start` reconciles persisted names on its next
snapshot. If the worker cannot run, sidebar metadata expires while tab names can
retain their last status until `start` or `stop` succeeds.

## Verification

```sh
python3 -m unittest tests.test_herdr_tab_status tests.test_herdr_shell tests.test_herdr_move_workspace -v
HERDR_CONFIG_PATH="$PWD/private_dot_config/herdr/config.toml" herdr config check
sh -n private_dot_local/bin/executable_herdr-shell
```

The socket tests cover state transitions, agent exits, multiple agents, manual
renames, lost replies, restoration, reordered tabs, compact summaries, singleton
startup, and metadata ownership. The live `preview` command reads runtime state
without changing tab labels, focus, or metadata.
