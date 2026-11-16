# Herdr attention navigation

Use `Alt+u` to visit the previous workspace needing attention and `Alt+o` to visit the next one. The existing `Alt+p` and `Alt+n` shortcuts still visit all workspaces. Attention navigation follows sidebar order, wraps once, and skips the current workspace. It focuses an eligible agent pane, preferring blocked, then done, then idle panes within each workspace. If no other workspace qualifies, it leaves focus unchanged.

Run `herdr-attention list` to inspect agent decisions, or add `--json` for machine-readable output. Names are escaped in text output. `herdr-attention next` and `herdr-attention previous` navigate directly. Add `--quiet` to suppress normal text output.

By default, native `idle`, `done`, and `blocked` agents qualify. A workspace qualifies when any one of its panes qualifies, even when another pane is working. Claude idle or done panes with a positive current background-work count are skipped. Native blocked panes qualify even when background work is running. Shell-only panes do not qualify.

Use `--states idle,blocked` to select a different set of native states. Supported states are `idle`, `done`, `blocked`, `working`, and `unknown`. Use `--include-busy-claude` to ignore Claude background activity, or `--claude-busy-pattern REGEX` to add a match against the current Claude footer. These options also apply to `list`.

Claude activity detection reads the current terminal text on demand. It recognizes the current permission control row and narrow live activity lines near the input box. Claude may change its display or report activity in an unrecognized form. Missing or ambiguous footer evidence keeps the pane eligible with an `unverified` reason. A chosen unverified pane also emits a warning. This filter does not change Herdr's sidebar state. The helper checks the chosen agent again before focus, but the agent can change state immediately afterward.

The managed sources and their deployed targets are:

- `private_dot_local/bin/executable_herdr-attention` to `/home/vimkim/.local/bin/herdr-attention`.
- `private_dot_config/herdr/config.toml` to `/home/vimkim/.config/herdr/config.toml`.
