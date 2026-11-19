# claude-account

Run Claude Code as one of several subscription accounts while all of them share
one config directory (`~/.claude`: settings, skills, `CLAUDE.md`, plugins, and
history). Requires Python 3.10 or newer. No Python packages are needed.

## Shortcuts

The shortcuts are executable commands in `~/.config/my-scripts/bin` on `PATH`.
Use them in a shell or as the command for a new Herdr tab.
After `herdr tab create`, use the returned root pane ID in
`herdr pane run <pane-id> 'ai2 --resume'`.

| Command | Account |
| --- | --- |
| `ai-login`, `ai` | The login stored by `/login` with full features. |
| `ai0` through `ai9` | The token saved for slot N with `claude-account add N`. |
| `aip` | `ai "read prompt.md and execute"`. |
| `ai-status` | All account nicknames, usernames, credential states, and available usage. |
| `ai-best` | Compare `ai-login` and saved numbered accounts from `ai0` up by remaining allowance. |
| `ai-round` | Rotate through saved numbered accounts from `ai0` up. Skip any with a current reading below 20%. |
| `herdr-new-tab-ai-best` | Run `ai-best` in a new tab in the current Herdr workspace. |
| `herdr-new-workspace-ai-best` | Run `ai-best` in a new Herdr workspace. |

`ai-login` and `ai` run `claude-account run login`. The numbered shortcuts run
`claude-account run N`. The launcher starts Claude with these options.

```sh
claude --settings "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/local-settings.json" \
       --dangerously-skip-permissions [your arguments]
```

Arguments pass through unchanged, so `ai2 -c` and `ai3 --resume` work.

## Choose an account

Run `ai-best` in any shell to choose an account and start Claude in place.
Use `ai-best -- --resume` to pass an option to Claude.
Use `ai-best --help` for examples and `ai-best --version` for the installed
picker version.

Run either Herdr launcher from a Herdr pane. The new pane starts in your
current working directory, and focus stays in your current pane.

The picker checks `ai-login` directly and reads the latest status-line
observations for saved tokens. It scores each account by the lower of its
five-hour and weekly remaining percentages. Ties favor more five-hour
allowance, then more weekly allowance. If both allowances tie, `ai-login`
comes first, followed by numbered accounts in ascending order.

The picker warns and skips an account if either known window is below 10%.
It treats missing or expired observations as unknown. Configured accounts
with unknown usage are eligible after candidates with two known percentages.
Once Claude reports a window below 10%, its status line shows
`Low allowance (<10%)`.

Run `ai-round` to spread launches across accounts. It starts Claude in the
current terminal. Use `ai-round --resume` to pass an option to Claude.

`ai-round` reads the local usage cache for saved slots from `ai0` up.
It skips a slot if either current window shows less than 20% remaining.
Missing or expired readings count as unknown, and slots with unknown readings
get a turn if neither known window is below 20%. The launcher reports unknown
allowance when it starts one of those slots. Claude's status line can record
usage after the first response.

Eligible slots that share a username or token get one turn. The command
chooses the next eligible slot number and wraps to the lowest. If no account
qualifies, the command exits without starting Claude.

Concurrent launches share the last selected slot in `round-robin.json` in the
account state directory. A file lock protects the selection and update. Each
launch releases the lock before starting Claude.

## Add an account

```sh
claude-account add 0 --label personal --username you@example.com
```

1. The command runs `claude setup-token` and prints a sign-in URL.
2. Open the URL in a browser signed in to the account for `ai0`. A private
   window avoids picking up the account that is already signed in.
3. Paste the printed token at the hidden prompt.
4. Start the account with `ai0`.

`--paste` skips `claude setup-token` and only reads a token you already have.
Without a terminal, the token is read from the first line of stdin.

Run account setup in a normal shell, outside an agent session, because
`claude setup-token` prints the token. On a remote server, open the printed URL
in your local browser. The report labels a supplied username as user-provided;
the setup-token cannot verify that identity.

## Manage accounts

```sh
claude-account list        # local slots, nicknames, and estimated token lifetimes
claude-account status login # stored /login account and available usage
claude-account status 2   # the saved team account
claude-account status --all
claude-account label 2 --username team@example.com
claude-account label 2 --label team
claude-account remove 2    # delete slot 2's token file
claude-account run 2 -c    # what `ai2 -c` runs
```

`list` prints `RENEW SOON` when a token has less than 30 days left. Run
`claude-account add N` again to replace it.

`label` updates only the supplied nickname or username. It preserves the token,
the original `added` date, and other account metadata. `add`, `label`, and
`remove` accept numbered slots starting at 0. Manage the login with Claude's
`/login` command.

## Read the account report

`ai-status` reports `ai-login`, `ai0`, `ai1`, and `ai2`, plus other saved numbered
slots. A missing or unreadable account stays visible. Each row
shows a nickname, a username and its source, the credential state, and any
available five-hour and weekly allowance remaining.

`ai-login` uses the nickname `/login`. Its username comes from the selected Claude
configuration's login metadata and is marked as cached. Numbered slots use their
saved `label` as the nickname and their optional `username` as user-provided
identity. Missing identity appears as unknown. The report does not copy the
shared login identity onto token accounts.

With `CLAUDE_CONFIG_DIR` set, login metadata comes from `.claude.json` inside
that directory. Without it, the report reads `~/.claude.json`.

Configured credentials have not necessarily been accepted by the server. The
report distinguishes local credential presence from a successful usage request.
It does not send a model request or refresh, replace, or renew credentials.

For the stored login, the command makes one HTTPS request with a five-second
timeout to Claude's private OAuth usage endpoint. This endpoint is an
implementation detail and can change. When available, the report shows
`100 - utilization` as the remaining percentage, the reset time, and the fetch
time. Missing or invalid readings appear as unavailable, separately for each
window. Permission errors, network errors, and rate limits show an explanation
without exposing server response bodies or credentials.

For numbered slots, the report reads the last status-line observation for each
window from the local cache. The report shows each current reading with its
source, reset time, and observation time. A missing or expired reading appears
as unavailable. The report makes no usage requests with setup-tokens.

To populate the cache, start a fresh numbered session, such as `ai2`, and
send a message. The status line records the windows Claude supplies after a
response. The saved setup-token is sufficient for this path. Check the cached
values with `claude-account status 2`.

A token's estimated expiration date is separate from subscription usage
remaining. The report keeps all rows when a usage lookup fails. Its exit
status does not indicate whether authentication succeeded.

## Shell renewal reminders

Interactive Bash logins and Nushell panes print a renewal reminder at most once
per local calendar day, shared across both shells. Stored logins warn from seven
days before the earliest possible expiry, and continue warning after expiry.
Unknown or unreadable renewal metadata also produces a daily reminder.

The reminder checks `~/.claude`, sibling `~/.claude*` directories containing
credentials, and `CLAUDE_CONFIG_DIR` when set. Each login names its config
directory and, when available, its email. A settings file passed with `--settings`
does not select another credential directory. Slots in `CLAUDE_ACCOUNTS_DIR`,
or its default state directory, are checked separately.

For Claude Code 2.1.318, the expiry window runs from three days before
`claudeAiOauth.refreshTokenExpiresAt` through that timestamp. `claude auth status`
reports the latest bound as `loginExpiresAt`. For example, a latest bound of
`2026-12-05T04:09:39.261Z` means a December 2–5 UTC window. The short-lived access
token's `expiresAt` is not the login deadline. Refreshing a token preserves or
shortens the stored deadline. A new `claude auth login` replaces it.

Setup-token slots warn within 30 days of their estimated expiry, one year after
the recorded `added` date. This is an estimate because pasted tokens may be older.
Renew those slots with `claude-account add N`. `claude auth login` renews the
stored login, not a slot's setup-token.

`claude-auth-renewal` reads a text cache in
`${XDG_CACHE_HOME:-$HOME/.cache}/claude-auth-renewal/notice`. If the cache is missing
or at least an hour old, it starts a background Python worker. The worker reads
local metadata, writes the cache atomically, and uses a lock to combine concurrent
requests. Neither path runs Claude, contacts an API, or stores tokens in the cache.
On the first run, a missing cache is ready for the next shell. A new login can
leave a reminder stale for up to an hour.

To refresh immediately after a login, run `claude-auth-renewal --refresh`.
The command updates the cache without printing a reminder or changing the daily
acknowledgement. The shell hooks do no work in non-interactive shells.

The three-day window comes from the installed 2.1.318 bundle, whose
`chunk-gdkqhwa0.js` reads the stored refresh expiry and whose warning code
subtracts three days. The [official 2.1.318 changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#21318)
documents `loginExpiresAt` and the ten-day warning threshold. Future Claude
versions may change the window. See [verification results](claude-auth-renewal-verification.md).

## How it works

One config directory stores one `/login` credential, so switching accounts
with `/login` asks for a new browser sign-in every time. Claude Code ranks
`CLAUDE_CODE_OAUTH_TOKEN` above the stored login, so `claude-account` sets that
variable for the launched process only:

- `ai-login` uses the stored `/login`.
- Every numbered slot requires its own saved token and passes that token.
- A missing numbered slot fails before starting Claude.
- The launcher removes inherited `CLAUDE_CODE_OAUTH_TOKEN`,
  `ANTHROPIC_AUTH_TOKEN`, and `ANTHROPIC_API_KEY` before selecting credentials.
  Token setup uses the same environment cleanup.

The launcher selects the initial credential. Claude Code's shared configuration
can still supply a stored-login fallback after an environment token fails. The
wrapper does not guarantee account isolation for the full session. Check
Claude's `/status` if account selection changes unexpectedly.

## Limits

- `claude setup-token` tokens can only make model requests. Remote Control and
  claude.ai connectors require `ai-login`. Locally configured MCP
  servers still work. The official docs ask for `claude auth login` before
  `--cloud` and `--teleport`, so use `ai-login` or `ai` for those.
- Tokens last about one year.
- `remove` deletes the local file only. It does not revoke the token; see
  [If a token leaks](#if-a-token-leaks).
- Some files under `~/.claude` and in `~/.claude.json` cache per-account or
  per-organization data, for example `policy-limits.json`,
  `remote-settings.json`, and `oauthAccount`. Accounts from different
  organizations may overwrite each other's cache. This behavior is not
  documented. Suspect these files first if an unexpected policy appears.
- Do not put `CLAUDE_CODE_OAUTH_TOKEN` in the `env` block of the shared
  `settings.json`. It would apply to every session.

## Secrets and chezmoi

The token directory is `$XDG_STATE_HOME/claude-accounts`, which defaults to
`~/.local/state/claude-accounts`. The file number is one higher than the command
number, so `ai0` uses `1.json`. Keeping the file numbers preserves existing
tokens and usage readings. Each file has mode 0600 and the directory has mode
0700. Set `CLAUDE_ACCOUNTS_DIR` to use another directory.

The token directory is outside the chezmoi source. `.chezmoiignore` also lists
it, so `chezmoi add` prints `warning: ignoring .local/state/claude-accounts/...`
and adds nothing. With a custom `CLAUDE_ACCOUNTS_DIR`, keep the directory out of
chezmoi yourself.

## If a token leaks

Anyone holding the token can send model requests on that account until it
expires or is revoked. Revoke it on claude.ai, signed in as that slot's account:

1. Open **Settings > Claude Code** and click the trash icon next to the token.
   The Help Center says this covers tokens created with `setup-token`.
2. If the token is not listed there, open **Settings > Account > Active
   sessions** and choose **Terminate** for that session.
3. As a last resort, **Log out** of all sessions in **Settings > Account**
   (web only). This also signs out the slot's other Claude sessions.

Then run `claude-account add N` to mint and store a new token. Deleting the
local file, `claude-account remove`, `/logout`, and `claude auth logout` do not
revoke a setup-token token. The docs do not say whether a password change
revokes it. For a Team or Enterprise seat, an admin can remove the member, but
the docs do not say whether that revokes existing tokens.

The token can leak through these paths on this machine:

- Claude Code transcripts are plaintext under `~/.claude/projects/`. Run
  `claude-account add` in a normal shell, not as `! claude-account add` inside
  a Claude session, because `claude setup-token` prints the token.
- Terminal scrollback and multiplexer logs keep the printed token.
- An `ai2` session holds the token in `CLAUDE_CODE_OAUTH_TOKEN`. Commands that
  session runs may inherit it (not verified), so avoid printing the environment
  there.

Sources: [Log out of all active sessions](https://support.claude.com/en/articles/10310342-how-do-i-log-out-of-all-active-sessions),
[Managing your active sessions](https://support.claude.com/en/articles/13124001-managing-your-active-sessions),
[Plaintext storage](https://code.claude.com/docs/en/claude-directory.md).

## More slots

For slots 10 and higher, use `claude-account run` with the slot number, such as
`claude-account run 10`.

## Sources and checks

Chezmoi manages the executable source at
`private_dot_config/my-scripts/bin/executable_claude-account` and deploys it to
`~/.config/my-scripts/bin/claude-account`. The `ai`, `ai-login`, numbered `aiN`,
`aip`, `ai-status`, and `ai-round` shortcuts link to `claude-account` in the same
directory. `ai-best` has its own executable in that directory.

Run the focused checks:

```sh
python3 -m unittest discover -s tests -p test_claude_account.py -v
python3 -m unittest discover -s tests -p test_claude_auth_renewal.py -v
```

Official references:

- [Log in with multiple accounts](https://code.claude.com/docs/en/authentication.md#log-in-with-multiple-accounts)
- [Generate a long-lived token](https://code.claude.com/docs/en/authentication.md#generate-a-long-lived-token)
- [Authentication precedence](https://code.claude.com/docs/en/authentication.md#authentication-precedence)
