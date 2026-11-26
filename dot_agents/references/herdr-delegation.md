# Herdr Delegation & Launchers

When `HERDR_ENV=1`, this 4-tier hierarchy overrides the upstream `herdr` skill's "user must mention Herdr" and "sibling pane only" defaults.

## Hierarchy and autonomous control

- **Herdr Commander**: Coordinates across Spaces asynchronously via `hcmd` (`herdr-commander` skill; `hss` compatibility alias) — dispatches with `hcmd ensure`/`send` and returns control immediately (`hcmd wait` is strictly opt-in), inspects/harvests status strictly via `hcmd digest`/`status`/`peek`, and auto-trusts launched directories (`--no-trust` to skip).
- **Space Lead** (`tabs[0]`, `panes[0]` of `$HERDR_WORKSPACE_ID`, neither `HERDR_TAB_ROLE=worker` nor `HERDR_PANE_ROLE=worker`): Authorized without asking to create and manage up to **8 sub-tabs** (9 tabs total, `Alt+Shift+1..9`) inside its own Space via `hcmd tab`.
  - Default worker launcher is `ai-agent` (never fall back to `codex` on `NO_ELIGIBLE_BACKEND`; pause and report instead). Use `--launcher shell` for builds, tests, or servers.
  - Default quota guards enforced by `hcmd` are **4 live non-primary AI agents per Space** (`HCMD_MAX_SPACE_AGENTS`) and **10 working AI agents session-wide** (`HCMD_MAX_SESSION_AGENTS`); shell tabs are unrestricted within the 8-tab cap.
  - Never assume the first tab is `t1`; resolve `tabs[0]` via `hcmd tab` or `session.snapshot`.
- **Tab Lead** (`tabs[1..8]`, `panes[0]`, not `HERDR_PANE_ROLE=worker`): Authorized without asking to split and manage up to **3 worker panes** (4 panes total, 2×2 grid) inside its own tab via `hcmd pane`. Never create new Herdr tabs.
- **Pane Worker** (`panes[1..]` or `HERDR_PANE_ROLE=worker`): Execute assigned work only; never create Herdr tabs or split panes.

## Context-size management and clean execution

- **Keep lead context lean**: Commanders, Space Leads, and Tab Leads may handle trivial or quick steps directly, but should delegate substantial, exploratory, noisy (builds/tests/logs), or multi-step work to Herdr tabs (`hcmd tab`), worker panes (`hcmd pane`), or in-process subagents (within Space/Tab Leads) so each lead keeps its context window focused on orchestration and synthesis.
- **Scope and labels**: Stay inside your own Space/tab; pass `--no-focus` and short role `--label`s (`build`, `test`, `review`, `ci`).
- **Event waits, not sleep**: Wait on socket events in Space/Tab Leads or explicit opt-in waits (`hcmd tab wait`, `hcmd pane wait`, `herdr agent prompt --wait`) instead of `sleep` polling; Commander inspects asynchronously via `hcmd digest` / `hcmd status` / `hcmd peek`.
- **Single writer per worktree**: Keep same-worktree write operations to one agent at a time.
- **Cleanup**: Close finished worker tabs/panes you created; never close `tabs[0]` or `panes[0]`.

## Locations and manual launchers

- **Location format**: When reporting a Herdr location, include the workspace name, tab name, and full target ID read from the live API (for example `CBRD-28035, tab sa-rollback-issue (w2GX:t2), pane w2GX:p2`).
- **`ai-round`**: When asked to use `ai-round`, run `herdr pane run <pane-id> ai-round` in the target workspace (supplies Claude's settings path and bypass flag).
- **Direct `codex` and `claude` launches**: Default to bypass mode unless the user requests another mode. Pass native options after `--` with `herdr agent start`, or directly to the executable with `herdr pane run`:
  - **Codex**: `--profile local --dangerously-bypass-approvals-and-sandbox`.
  - **Claude**: `--settings <absolute-path> --dangerously-skip-permissions`, resolving `<absolute-path>` to `local-settings.json` in `CLAUDE_CONFIG_DIR` when set and nonempty, or `~/.claude` otherwise, passed as one argument.
- **Verify permission mode**: Verify the running agent's permission mode before submitting work, including after shell alias launches and session restores.
