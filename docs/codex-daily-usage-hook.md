# Codex daily usage hook

**Status: disabled.** The `UserPromptSubmit` and `Stop` entries were removed
from `dot_codex/hooks.json.tmpl` on October 13, 2026. The helper script is
kept; restore the entries below to re-enable the guard.

The daily guard runs through normal Codex lifecycle hooks. It warns after 25
weekly percentage points of observed daily consumption and rejects new prompts
at 33. The accounting day changes at midnight in `Asia/Seoul`.

Use Codex normally after enabling the two hooks. The existing session hook,
shell aliases, and model settings are preserved.

## Configuration

The managed `~/.codex/hooks.json` adds a command to `UserPromptSubmit` and `Stop`:

```text
python3 '/home/vimkim/.codex/hooks/daily-usage.py' hook --daily-cap 33 --warn-at 25
```

Change the two numbers in the source `dot_codex/hooks.json.tmpl` to change the
thresholds. Set `--warn-at` below `--daily-cap`, and keep both events consistent.
For October 13, 2026 in `Asia/Seoul`, the helper's `CAP_BY_DAY` exception raises
the usual 33-point cap to 66. It automatically returns to 33 at midnight on
October 14. Other explicitly configured caps still apply, and recorded usage
is preserved.

There is no documented native daily quota key in Codex configuration; the helper
implements the check using the quota telemetry established in the
[research note](codex-daily-usage-guard-research.md).

Codex requires a one-time review of new hook definitions in `/hooks` before they
run. Review and trust the `UserPromptSubmit` and `Stop` entries after deployment.
Changed hook definitions need review again. Hooks are currently enabled in this
account's deployed configuration. On other installations, enable them with
`[features] hooks = true` if necessary.
[Official hook documentation](https://learn.chatgpt.com/docs/hooks)

Activation stores the reviewed hooks' enabled flags and definition hashes in
Codex's runtime settings. Other saved settings are preserved; the repository's
base `config.toml` is not applied to perform activation.

The prompt hook returns `decision: "block"` at the cap. The Stop hook returns
`continue: false` to prevent hook-driven continuation; a Stop decision of
`"block"` would instead continue the turn. These hooks do not interrupt work
already running. [Official hook behavior](https://learn.chatgpt.com/docs/hooks)

## Daily accounting

Each invocation reads current account quota metadata through a temporary Codex
app-server connection, with its own hooks disabled. It does not start inference.
The helper finds the seven-day quota window by duration, whether it is in
`primary` or `secondary`. Percentages come from Codex, rather than token counts.
[App-server reference](https://learn.chatgpt.com/docs/app-server)

State is private, account-scoped, and shared by concurrent local sessions under
`${XDG_STATE_HOME:-~/.local/state}/codex-daily-guard/`. File locking and atomic
replacement prevent concurrent hooks from losing or double-counting updates.

Without a background collector, exact midnight usage cannot be reconstructed.
The first reading conservatively counts the current weekly percentage toward
today. Later days count the entire increase since the previous reading toward
the new day, including the gap around midnight. This can block earlier than
intended, especially on first installation or after a long gap.

A quota reset between readings makes the day's total incomplete. The guard
keeps known consumption and denies new prompts until the next day has a usable
baseline, or you explicitly supply today's consumption. Plan changes and
unexplained decreases are treated as unknown too. Missing metadata or invalid
state produces a blocking hook response.

For an inspection:

```sh
python3 ~/.codex/hooks/daily-usage.py status
```

If you know today's consumption and deliberately want to correct a conservative
or unknown baseline, supply it explicitly:

```sh
python3 ~/.codex/hooks/daily-usage.py baseline --used-today 8
```

This is a manual override. State records the prior total and uncertainty with
the correction; do not use an arbitrary zero to claim earlier usage was free.

The guard applies to local clients loading and trusting these hooks. Unguarded
clients, disabled hooks, helper launch failures, cloud jobs, delayed quota
reports, and already-running turns prevent a strict account-wide cap. Codex's
integer percentages also limit precision.

## Managed targets and integration

| Source | Absolute deployed target on this server |
| --- | --- |
| `dot_codex/hooks/executable_daily-usage.py` | `/home/vimkim/.codex/hooks/daily-usage.py` |
| `dot_codex/hooks.json.tmpl` | `/home/vimkim/.codex/hooks.json` |

After approved local integration, apply each target separately from the merged
checkout, script first. Review each file's `chezmoi diff`, then apply it and
verify the diff is empty. Use `/hooks` to review the new entries and restart
existing sessions so they load the added hook definitions. The base
`~/.codex/config.toml` has unrelated live settings and is not an apply target.

## Verification

```sh
python3 -B -m unittest discover -s tests -p test_codex_daily_guard.py -v
python3 -B tests/verify_codex_daily_guard_hook.py
```

Focused tests cover thresholds, midnight gaps, missed days, resets, account and
plan changes, stale data, private state, concurrent processes, manual correction,
prompt rejection, and Stop output, including invalid argument handling.

Native verification uses installed Codex 0.162.1 with ignored user configuration,
a disposable thread, fixture quota, and a localhost provider. At the simulated
33-point cap, the hook helper ran, the turn completed with zero token usage, and
the provider received zero POST requests. The headless JSON CLI does not expose
the rejection reason in its standard events, so this check also verifies the
helper's persisted fixture state. No OpenAI inference was used.

The helper's live metadata path was also checked successfully using a scratch
state directory. Activation of the new global definitions still requires
deployment and native hook trust; that is distinct from this fixture test.
