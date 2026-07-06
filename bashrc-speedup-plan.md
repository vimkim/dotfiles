# Bashrc Speedup Plan

Date: 2026-07-06

## Goal

Keep Bash cheap for automation and coding-agent command execution while preserving a usable fallback Bash prompt when explicitly opened by a human.

Primary shells for rich interactive use are Nushell and zsh, so Bash should default to:

- Fast environment setup.
- No prompt framework or line editor in agent/script contexts.
- No eager language/tool managers unless they are actually needed.
- Human-only aliases, completion, prompt, history UI, and line editing.

## Current Baseline

Measured from `/home/vimkim/.local/share/chezmoi` with 10 runs where practical.

| Item | Average |
| --- | ---: |
| `bash -i -c exit` with current `dot_bashrc` | 0.293 s |
| Bare `bash --noprofile --norc -i -c exit` | 0.003 s |
| Source `/etc/bashrc` only | 0.122 s |
| `eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"` only | 0.062 s |
| `eval "$(starship init bash)"` only | 0.015 s |
| `eval "$(atuin init bash)"` only | 0.010 s |
| `eval "$(zoxide init bash)"` only | 0.006 s |
| Source `$HOME/.cargo/env` only | 0.003 s |
| Source `$HOME/.local/bin/env` only | 0.003 s |

Notes:

- `nvm` is no longer used and should not appear in Bash startup.
- `fzf` is available through PATH; Bash does not need to source `~/.fzf.bash`.
- `blesh` is not needed for Bash and should be removed instead of TTY-gated.
- `/etc/bashrc` sources about 20 `/etc/profile.d/*.sh` files. The slowest observed pieces were `scl-init.sh`, `modules.sh`, and `flatpak.sh`.
- `/etc/bashrc` also sources system Nix on this host. Prefer controlling whether `dot_bashrc` sources `/etc/bashrc`; do not manage `/etc/bashrc` itself from this chezmoi repo.

## Applied Changes

The current chezmoi `dot_bashrc` now:

- Replaces eager `brew shellenv` with static Homebrew environment variables and PATH entries.
- Removes the local Nix installer source line.
- Removes `nvm`, `~/.fzf.bash`, and `blesh`.
- Keeps `mise` out of Bash startup.
- Returns early for non-interactive shells.
- Returns early for non-TTY interactive shells, so agent-style `bash -i -c ...` skips `/etc/bashrc`, zoxide, starship, atuin, aliases, and prompt/history UI.
- Leaves `/etc/bashrc` untouched and only sources it for human Bash sessions.

Measured pending chezmoi version with `bash --rcfile dot_bashrc -i -c exit`: 0.0032 s average over 20 runs.

## Original Problems In `dot_bashrc`

Line references are from the original `dot_bashrc` before the applied cleanup.

- Lines 4-6 source `/etc/bashrc` before any local fast path. This costs about 120 ms and runs system profile scripts even for non-TTY agent shells.
- Line 8 runs `brew shellenv` on every Bash startup. This costs about 60 ms and can be replaced by static environment variables or cached generated output.
- Lines 205-279 are mostly bash-it configuration comments and exports. `bash-it` is not sourced, `BASH_IT` points at `/home/cubrid/.bash_it`, and this block looks like dead historical config.
- Line 296 runs `whoami` and overwrites `USER`. `USER` is normally already set by the session; avoid an external process and avoid overriding it.
- Lines 48 and 301 both add `$HOME/.local/bin` through different mechanisms.
- Line 88 has a typo: `alias la=' -lAF'`.
- Lines 111 and 282 duplicate `alias c='cd'`; lines 176 and 284 duplicate `alias v='nvim'`.
- Line 117 likely intends `cd -`, but currently uses `cd -$OLDPWD`.
- `mc()` uses unquoted `$@` and then `cd $@`; this is fragile for paths with spaces or multiple arguments.
- The fzf aliases use `fdfind`, but this machine currently has `fd`, not `fdfind`.

## Target Shape

Refactor `dot_bashrc` into three tiers.

### Tier 1: Minimal Environment, Always Safe

This section should be at the top and should avoid external commands where possible.

Keep only environment that scripts and agent shells need:

- `EDITOR=nvim`
- Stable `PATH` entries:
  - `$HOME/.local/bin`
  - `$HOME/.cargo/bin`
  - `/opt/nvim-linux64/bin`
  - `/home/linuxbrew/.linuxbrew/bin`
  - `$HOME/.nix-profile/bin` if needed
  - `$HOME/.config/my-scripts/bin` if needed by agents
- `MY_SCRIPTS="$HOME/.config/my-scripts"` if command scripts rely on it.

Use a small `path_prepend` helper instead of repeated raw `export PATH=...`.

Avoid `brew shellenv` in this tier. For the current Linuxbrew prefix, use static exports:

```bash
export HOMEBREW_PREFIX="/home/linuxbrew/.linuxbrew"
export HOMEBREW_CELLAR="/home/linuxbrew/.linuxbrew/Cellar"
export HOMEBREW_REPOSITORY="/home/linuxbrew/.linuxbrew/Homebrew"
path_prepend "$HOMEBREW_PREFIX/bin" "$HOMEBREW_PREFIX/sbin"
```

Only keep `brew shellenv` as an explicit fallback function or cache refresh command.

### Tier 2: Automation Stop

Return early unless this is an interactive shell:

```bash
case $- in
  *i*) ;;
  *) return ;;
esac
```

Then return early for non-TTY interactive shells, unless explicitly forced:

```bash
if [[ -z ${BASH_FULL_INIT:-} && ( ! -t 0 || ! -t 1 ) ]]; then
  return
fi
```

This is the key speedup for Claude/Codex-style `bash -i -c ...` command execution. Those shells should get PATH and core env, but not aliases, prompt frameworks, completion, or history UI.

Expected target: non-TTY `bash -i -c exit` should drop from about 293 ms to under 20 ms.

### Tier 3: Human Bash Only

Only after the non-TTY guard:

- Source `/etc/bashrc` if you still want system Bash behavior in human Bash sessions.
- Define aliases and interactive helper functions.
- Source completion files.
- Initialize zoxide, starship, and atuin.

Guard every optional tool with `command -v` or file checks.

## Caching Plan

Port the zsh `_cached_source` pattern to Bash for generated shell snippets.

Use it for:

- `zoxide init bash`
- `starship init bash`
- `atuin init bash`
- optionally `brew shellenv` if static Homebrew exports are not enough

Sketch:

```bash
_bash_cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/bash-init"
mkdir -p "$_bash_cache_dir"

_cached_eval() {
  local name=$1
  shift
  local cache="$_bash_cache_dir/$name.bash"

  if [[ ! -s $cache ]]; then
    "$@" > "$cache" 2>/dev/null || {
      rm -f "$cache"
      return 1
    }
  fi

  # shellcheck source=/dev/null
  source "$cache"
}

bash-cache-refresh() {
  command rm -rf "$_bash_cache_dir"
}
```

Then:

```bash
command -v zoxide >/dev/null 2>&1 && _cached_eval zoxide zoxide init bash
command -v starship >/dev/null 2>&1 && _cached_eval starship starship init bash
command -v atuin >/dev/null 2>&1 && _cached_eval atuin atuin init bash
```

## Removed Bash Integrations

These should stay out of Bash startup:

- `nvm`: no longer used.
- `mise`: used elsewhere, but Bash does not need to activate it.
- `blesh`: removed.
- `~/.fzf.bash`: not needed because `fzf` is available from PATH.

For local aliases that call `fzf`, detect `fd` versus `fdfind` once:

```bash
if command -v fd >/dev/null 2>&1; then
  _fd_cmd=fd
elif command -v fdfind >/dev/null 2>&1; then
  _fd_cmd=fdfind
fi
```

## Cleanup Plan

1. Remove or quarantine the unused bash-it block.
2. Remove `export USER=$(whoami)`.
3. Deduplicate aliases.
4. Fix `alias la`.
5. Replace `alias back='cd -$OLDPWD'` with `alias back='cd -'`.
6. Make `mc()` accept exactly one directory argument:

```bash
mc() {
  mkdir -p -- "$1" && cd -- "$1"
}
```

7. Consider not aliasing `cd` to `cl` in Bash. It makes every directory change run `ls`, which is convenient for humans but surprising for agent commands and scripts.
8. Keep safety aliases like `cp -i` and `mv -i` human-only.

## Proposed Implementation Order

1. Done: add `path_prepend`, minimal env, and static Homebrew PATH setup at the top.
2. Done: move the non-interactive guard immediately after minimal env.
3. Done: add the non-TTY interactive guard with `BASH_FULL_INIT=1` override.
4. Done: move `/etc/bashrc` below the non-TTY guard.
5. Done: keep `nvm`, `mise`, `blesh`, and `~/.fzf.bash` out of Bash startup.
6. Optional: add `_cached_eval` for zoxide, starship, and atuin in human Bash sessions.
7. Optional: remove dead bash-it config and cleanup duplicate/buggy aliases.
8. Done: run syntax and startup checks.

## Verification

Syntax:

```bash
bash -n dot_bashrc
```

Startup timing:

```bash
for i in 1 2 3 4 5; do
  /usr/bin/time -f '%e real %U user %S sys' bash -i -c exit >/dev/null
done
```

Human full-init escape hatch:

```bash
BASH_FULL_INIT=1 bash -i
```

Chezmoi preview:

```bash
chezmoi diff
```

Expected results:

- Agent/non-TTY `bash -i -c exit`: about 3 ms when using the pending `dot_bashrc`.
- Human Bash with `BASH_FULL_INIT=1` or a real terminal: still gets prompt, aliases, zoxide, starship, and atuin.
- `fzf` remains a PATH-provided command; Bash does not source `~/.fzf.bash`.
- No `stty` warning in non-TTY shells because `atuin init bash` is skipped.
