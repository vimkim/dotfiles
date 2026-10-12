# Codex daily usage guard research

Status: researched on 2026-10-12. Scope: a personal ChatGPT Pro account and
local Codex use. This records official OpenAI documentation, a read-only local
probe, and a proposed design. No guard has been implemented or deployed.

A local guard is feasible: observe the account's weekly usage percentage and
reject new local prompts after the day's consumption reaches 33 percentage
points. An exact cap across the entire account would need service-side
enforcement. An account-wide, daily percentage setting was **not found in the
reviewed documentation**; this is a bounded research finding, not proof that
every account UI lacks it. The reviewed references include
[pricing](https://learn.chatgpt.com/docs/pricing),
[configuration](https://learn.chatgpt.com/docs/config-file/config-reference),
[desktop settings](https://learn.chatgpt.com/docs/app/settings), and
[app-server methods](https://learn.chatgpt.com/docs/app-server).

## What 33% means

Assume a calendar day from midnight to midnight in `Asia/Seoul`, and 33% of the
**total** weekly included allowance. For example, starting the day at 7% weekly
usage gives a nominal stop point at 40%. This is 33 percentage points, not 33%
of the remaining 93%, which would allow only 30.69 percentage points.

At 33% daily, three full days consume 99% and only 1% remains for the fourth
day. This prevents a single-day binge; it does not reserve capacity for the
whole week. Even pacing would be 20% over five workdays or about 14.3% over
seven days. A rolling 24-hour cap would be a different policy.

## Documented controls and signals

| Capability | Finding |
| --- | --- |
| Pro usage windows | Pro currently has no five-hour limit. Plus and Standard Business retain five-hour estimates; weekly limits may apply. Allowance consumption depends on model, task, context, and other factors. Check the account dashboard for actual windows. [Pricing](https://learn.chatgpt.com/docs/pricing) |
| Connected-app caps | Settings > Usage supports a weekly percentage cap for each external app authorized to use a ChatGPT plan. It is a cap on that app's use, not a reserved allocation. This does not document a daily cap on all Codex activity. [Sign in with ChatGPT](https://learn.chatgpt.com/docs/sign-in-with-chatgpt) |
| Rollout budgets | `features.rollout_budget.*` is under development, disabled by default, and tracks weighted tokens with a token limit. The reference does not document a mapping to a percentage of personal weekly quota or a daily account cap. [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) |
| Enterprise budget releases | The September 19, 2026 cookbook releases Enterprise/Edu monthly credit or USD budgets on hourly, daily, or weekly schedules using the ChatGPT Admin API. It does not establish access to this control for personal Pro included quota. [Budget release cookbook](https://developers.openai.com/cookbook/examples/chatgpt/daily_usage_limits/readme) |
| Workspace spend controls | These apply to eligible workspace-credit activity, can include some Codex usage, and do not cover all Codex usage or Platform API billing. [Workspace usage controls](https://learn.chatgpt.com/docs/enterprise/usage-limits) |

The app-server documents `account/rateLimits/read` and
`account/rateLimits/updated`. Windows expose `usedPercent`,
`windowDurationMins`, and `resetsAt`; the last is a Unix timestamp in seconds.
`rateLimitsByLimitId` supplies multiple metered buckets when present.
`account/usage/read` supplies token activity and optional daily token buckets,
but does not document daily included-quota percentages. `turn/interrupt`
requests cancellation of an active turn. These are useful building blocks,
not a documented daily-budget setter. A historical midnight quota-percentage
baseline was not found in these methods.
[App-server reference](https://learn.chatgpt.com/docs/app-server)

Synchronous `UserPromptSubmit` hooks can reject a prompt with
`decision: "block"` or exit code `2`. A `Stop` hook's
`decision: "block"` instead creates a continuation; use `continue: false`
to prevent those continuations at the cap. User hooks require trust and can
be disabled. Background hooks cannot block. Tool hooks miss hosted tools such
as WebSearch and some specialized paths, so they are not a complete boundary.
`SubagentStart` with `continue: false` does not prevent a subagent from starting.
Transcripts are not a stable hook interface.
[Hooks](https://learn.chatgpt.com/docs/hooks)

## Local verification

On 2026-10-12, the installed standalone
`/home/vimkim/.local/bin/codex` reported `codex-cli 0.162.1`.
The local inspection performed these read-only steps:

1. Generate the app-server JSON schema with the installed binary.
2. Start `codex app-server --stdio` with analytics and hooks disabled for this
   metadata-only invocation, using existing authentication.
3. Send the `initialize` request, then the `initialized` notification.
4. Call `account/rateLimits/read`, sanitize the response, and stop the process.
   Do not start a thread or invoke a model.

The returned account signal was:

```json
{
  "planType": "pro",
  "limitId": "codex",
  "primary": {
    "usedPercent": 7,
    "windowDurationMins": 10080,
    "resetsAt": 1792386195
  },
  "secondary": null
}
```

`rateLimitsByLimitId.codex` returned the same window. `10080` minutes is seven
days; the reported reset was 2026-10-19 at 14:03:15 in `Asia/Seoul`. This
confirms that this account currently exposes its weekly window in `primary`.
**Do not assume `secondary` is the weekly window.** The generated schema uses
an integer `usedPercent`; reset and duration fields can be null. It also
confirms that `turn/interrupt` requires `threadId` and `turnId`. This verifies
available telemetry and schema, not interruption or hook behavior.

The existing Bash, Zsh, and Nushell `cx`/`cxp` aliases invoke Codex directly.
The source [Codex configuration](../dot_codex/private_config.toml) already
includes `weekly-limit` in the status line. Deployed configuration has hook
enablement and a trusted SessionStart hook that differ from the source;
model settings also differ. Preserve that unrelated drift when implementing
anything later. This report is excluded from deployment by `docs/**` in
`.chezmoiignore` and has no deployed target.

## Proposed local design

The following is an engineering proposal, not a native OpenAI feature or a
tested implementation.

1. Maintain one local collector and durable state per account, with atomic
   updates and a lock shared by concurrent sessions. Read fresh quota metadata
   before admitting work; optionally monitor updates between requests. A
   metadata-only helper must disable its own hooks to avoid recursively
   invoking the guard. Do not estimate included quota from tokens or API prices.
2. Select the intended metered bucket and discover its weekly window from
   duration and reset metadata, checking both `primary` and `secondary`.
   A missing or ambiguous window means unknown usage. Do not add percentages
   from different buckets: their denominators may differ.
3. Persist the percentage at the start of each KST day. Within an unchanged
   quota window, today's usage is the current percentage minus that baseline.
   A collector must retain observations across process restarts. Taking the
   first afternoon sample as midnight would silently forgive earlier usage.
4. Carry the day's consumption across weekly resets, including any earned
   reset. A quota reset does not reset the daily guard. Track each observed
   window segment separately and add its consumption. If the collector misses
   usage around a reset, or a plan change alters the denominator, mark the
   day's total unknown rather than inventing an exact value.
5. Warn at an optional 25-point threshold. At 33 points, reject subsequent
   prompts and prevent automatic Stop continuations until the next KST day.
   Display observed consumption, remaining daily capacity, and the next
   unblock time. A deliberate override could be recorded separately.
6. On stale telemetry or a missing baseline, return an explicit supported
   denial until refreshed or deliberately overridden. A script crash, skipped
   hook, or hook timeout must not be assumed to deny work; verify failure
   behavior before treating this as dependable protection.

This design gives an admission guard for clients loading the trusted hooks.
A launcher that checks only once cannot govern later prompts in that session.
A warning in `AGENTS.md` is a behavioral reminder, not executable enforcement.

For mid-turn stopping, a stronger design would run work through a controlled
app-server client that monitors usage and requests `turn/interrupt` for its
active turns when the threshold is observed. That requires a client or
supervisor integration; the existing interactive CLI aliases do not provide
that integration merely by invoking a metadata probe. Cancellation also needs
a policy for work left incomplete.

## Practical limits and next validation

A prompt admitted at 32% daily consumption can run past 33%. Official pricing
even permits an active turn to continue after the account's native limit,
subject to fair use. [Pricing](https://learn.chatgpt.com/docs/pricing)
Integer percentages, delayed reports, concurrent requests, and already-started
work prevent a verified exact 33.00% local cap. The reviewed docs do not
establish a reporting latency or rounding guarantee.

Account telemetry can reveal other consumption, but local hooks cannot block
another computer, a phone, cloud jobs, or unguarded clients. Multi-device
protection needs shared state and enforcement on every participating client;
only a service-side cap could cover the whole account automatically. A guard
for included allowance also needs to distinguish paid credits and API-key use.

Before implementation is considered reliable, validate midnight baselines,
weekly resets, missing metadata, account changes, concurrent sessions,
hook trust/disablement, automatic continuations, long turns, and interruption.
The research probe consumed no inference turn; none of those guard behaviors
has been tested. The practical next step is a local prototype with those
cases and a clearly stated allowance for overshoot.
