# claude-account

Run Claude Code as one of several subscription accounts while all of them share
one config directory (`~/.claude`: settings, skills, `CLAUDE.md`, plugins, and
history). Requires Python 3.10 or newer. No Python packages are needed.

## Shortcuts

Bash, Zsh, and Nushell define the same shortcuts:

| Command | Account |
| --- | --- |
| `ai`, `ai1` | Slot 1: the login stored by `/login` (full features). |
| `ai2` … `ai5` | Slot N: the token saved with `claude-account add N`. |
| `aip` | `ai "read prompt.md and execute"`. |

Each shortcut runs `claude-account run N`, which starts:

```sh
claude --settings "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/dotfiles-settings.json" \
       --dangerously-skip-permissions [your arguments]
```

Arguments pass through unchanged, so `ai2 -c` and `ai3 --resume` work.

## Add an account

```sh
claude-account add 2 --label personal
```

1. The command runs `claude setup-token` and prints a sign-in URL.
2. Open the URL in a browser signed in to the account for slot 2. A private
   window avoids picking up the account that is already signed in.
3. Paste the printed token at the hidden prompt.
4. Start the account with `ai2`.

`--paste` skips `claude setup-token` and only reads a token you already have.
Without a terminal, the token is read from the first line of stdin.

## Manage accounts

```sh
claude-account list        # slots, label, and days left on each token
claude-account status 2    # what `claude auth status` reports for slot 2
claude-account remove 2    # delete slot 2's token file
claude-account run 2 -c    # what `ai2 -c` runs
```

`list` prints `RENEW SOON` when a token has less than 30 days left. Run
`claude-account add N` again to replace it.

## How it works

One config directory stores one `/login` credential, so switching accounts
with `/login` asks for a new browser sign-in every time. Claude Code ranks
`CLAUDE_CODE_OAUTH_TOKEN` above the stored login, so `claude-account` sets that
variable for the launched process only:

- A slot with a saved token passes that token.
- Slot 1 without a token uses the stored `/login`. Any inherited
  `CLAUDE_CODE_OAUTH_TOKEN` is removed first, so `ai1` launched inside an `ai2`
  session still uses the stored login.
- Any other slot without a token fails before starting Claude.
- `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_API_KEY` outrank the slot token. The
  command warns when either is set.

## Limits

- `claude setup-token` tokens can only make model requests. Remote Control and
  claude.ai connectors do not work in `ai2` and higher. Locally configured MCP
  servers still work. The official docs ask for `claude auth login` before
  `--cloud` and `--teleport`, so use slot 1 for those.
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

Tokens are stored as `$XDG_STATE_HOME/claude-accounts/N.json`, which defaults
to `~/.local/state/claude-accounts/N.json`. Each file has mode 0600 and the
directory has mode 0700. Set `CLAUDE_ACCOUNTS_DIR` to use another directory.

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

The shortcuts stop at `ai5`. To add more, extend the slot list in
`dot_bashrc` and `private_dot_config/my-scripts/zsh/aliases.zsh`, and add
`alias aiN = claude-account run N` lines in
`private_dot_config/nushell/alias.nu`. Without a shortcut,
`claude-account run 6` works for any slot.

## Sources and checks

Chezmoi manages the executable source at
`private_dot_config/my-scripts/bin/executable_claude-account` and deploys it to
`~/.config/my-scripts/bin/claude-account`, which is already on PATH.

Run the focused checks:

```sh
python3 -m unittest discover -s tests -p test_claude_account.py -v
```

Official references:

- [Log in with multiple accounts](https://code.claude.com/docs/en/authentication.md#log-in-with-multiple-accounts)
- [Generate a long-lived token](https://code.claude.com/docs/en/authentication.md#generate-a-long-lived-token)
- [Authentication precedence](https://code.claude.com/docs/en/authentication.md#authentication-precedence)
