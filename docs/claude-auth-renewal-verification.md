# Claude renewal reminder verification

Verified on 2026-11-05 with Claude Code 2.1.318, Nushell 0.115.1, and
`/usr/bin/bash` 5.1.8. Source changes were tested in a disposable home before
deployment. The comparison baseline is dotfiles commit `20cf0db`.

## Expiry evidence

The installed Claude binary contains these calculations:

- `chunk-gdkqhwa0.js`, `tqn()`, reads `claudeAiOauth.refreshTokenExpiresAt`
  from a stored renewable login. It rejects implausible dates and access-token
  expiries more than three days beyond that bound.
- `chunk-gvr4gxa7.js`, `s2n()`, exports that timestamp as
  `credential_expires_at`. `claude auth status` uses it for `loginExpiresAt`.
- The warning formatter subtracts `3 * 86400000` milliseconds for the earliest
  date. The warning starts ten days before the latest date, or seven days before
  the earliest date.
- The credential update code preserves the earlier deadline on a token refresh
  with `Math.min(old, refreshed)`. A new sign-in replaces the deadline.

A live `claude --settings ~/.claude/dotfiles-settings.json auth status` returned
`2026-12-05T04:09:39.261Z`. The stored refresh expiry matched it, giving a
December 2–5 UTC window. The separate slot-2 setup-token returned an auth method
of `oauth_token`, with no email or `loginExpiresAt`. No tokens were printed.

The [official 2.1.318 changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#21318)
documents the new expiry fields and ten-day warning. The three-day calculation
is evidence from this installed version rather than a documented API guarantee.

## Behavior checks

The focused suite passes 22 tests, including the existing account-wrapper tests:

```sh
python3 -m unittest discover -s tests -p 'test_claude*.py' -v
bash -n dot_bashrc private_dot_config/my-scripts/bin/executable_claude-auth-renewal
shellcheck private_dot_config/my-scripts/bin/executable_claude-auth-renewal
```

Real interactive Bash logins and Nushell processes run in pseudo-terminals with
the proposed startup files. Simulated credentials whose latest bound is
November 9 produce a November 6–9 UTC reminder in each shell. Both shells share
one daily acknowledgement. Twelve concurrent helper processes print one notice
in total. Tests also cover background cache creation, separate config directories,
setup-token estimates, expired logins, missing dates, malformed metadata, and
secret exclusion from output and cache files.

`bash -c true`, `bash -lc true`, and `nu -c 'true | ignore'` produce zero stdout
and stderr bytes. Literal `nu -c true` produces its normal five-byte `true\n`
result. None of these commands acknowledges or refreshes a deliberately stale
reminder cache.

`strace -f -e trace=process,openat` on the fresh-cache helper shows one executable,
the helper itself. It starts no Python or Claude process and opens no credential
file. Its work is shell startup and a cached text-file read.

## Startup measurements

The harness alternates before and after runs, discards one warmup per side, and
checks exit codes and output. The following values are medians of 20 runs per
side. Each range is the minimum through maximum, in milliseconds.

| Command | Before, ms | After, ms |
| --- | --- | --- |
| `bash -c true` | 1.726 [1.562, 2.165] | 1.754 [1.660, 2.806] |
| `bash -lc true` | 121.526 [114.782, 126.882] | 122.131 [116.167, 128.368] |
| `nu -c 'true \| ignore'` | 28.757 [25.463, 30.438] | 28.940 [25.050, 32.065] |
| Interactive Bash login | 211.052 [203.040, 233.167] | 217.028 [208.837, 230.583] |
| Interactive Nushell | 144.868 [135.558, 153.070] | 149.085 [138.950, 152.653] |

The cached helper alone takes 2.017 ms [1.895, 2.305]. Non-interactive timings
show no measurable change. Interactive medians rise by about 4–6 ms, with
overlapping ranges. These are observations rather than a hard latency bound.
The host has 80 logical CPUs and had load averages of 9.22, 38.59, and 36.82.
Alternating samples reduces the effect of other work on the host.

Interactive measurements use a fresh cache with no due reminder and the complete
source startup files. Unrelated prompt, history, fetch, and daily-update commands
are stubbed in the disposable home. Bash receives a real terminal. Nushell uses
`--config ... -i -c` to load its full interactive config without timing input.
A separate near-expiry run confirms that this measured path invokes the reminder.

Reproduce the comparison from the task checkout:

```sh
python3 tools/benchmark_claude_auth_renewal.py --before-ref 20cf0db --runs 20
```

## Deployment scope

The source changes map to these deployed targets:

- `dot_bashrc` to `~/.bashrc`.
- `private_dot_config/nushell/config.nu` to `~/.config/nushell/config.nu`.
- `private_dot_config/my-scripts/bin/executable_claude-auth-renewal` to
  `~/.config/my-scripts/bin/claude-auth-renewal`.
- `private_dot_config/my-scripts/claude_auth_renewal.py` to
  `~/.config/my-scripts/claude_auth_renewal.py`.

Each target was inspected with `chezmoi --source <task-checkout> diff -- <target>`.
Both existing targets have only the proposed reminder additions. Both helper
targets are new. Deployment and final deployed-target verification await merge
approval. The cache is generated on the next interactive startup and becomes
available for subsequent shells. Refreshes can lag a new login by up to an hour.
