#!/usr/bin/env bash
# Claude Code status line — built entirely from Claude Code's own session
# JSON (schema: https://code.claude.com/docs/en/statusline), not from the
# user's Starship prompt. Login shell is nushell, so this is a plain bash
# script with an explicit shebang, invoked as `bash statusline.sh`.
#
# Shows: model name, current directory + git branch (+ GitHub PR number),
# context window usage, 5h/7d rate-limit remaining, and (on a second line)
# the last prompt.
#
# Kept fast/non-blocking: single jq pass over stdin, only cheap read-only
# git metadata calls (no status/diff), and --no-optional-locks so it never
# contends with other git processes running in the same worktree.

set -uo pipefail

input="$(cat)"

# --- locate jq robustly (statusline runs with a minimal PATH on some setups) ---
JQ="$(command -v jq 2>/dev/null)"
for cand in /home/linuxbrew/.linuxbrew/bin/jq /usr/bin/jq /usr/local/bin/jq /opt/homebrew/bin/jq; do
  [ -n "$JQ" ] && break
  [ -x "$cand" ] && JQ="$cand"
done

# --- working directory for this session (drives directory/git/custom modules) ---
cwd="$PWD"
if [ -n "$JQ" ]; then
  extracted="$(printf '%s' "$input" | "$JQ" -r '.workspace.current_dir // .cwd // empty')"
  [ -n "$extracted" ] && cwd="$extracted"
fi

# --- directory (full path, ~ shortened) + git branch for that directory ---
dir_display="$cwd"
case "$dir_display" in
  "$HOME") dir_display="~" ;;
  "$HOME"/*) dir_display="~${dir_display#"$HOME"}" ;;
esac

git_branch=""
if command -v git >/dev/null 2>&1; then
  # Cheap metadata reads only (symbolic-ref/rev-parse) — no status/diff — and
  # time-boxed so a stalled/networked filesystem can never block the prompt.
  gtimeout() { if command -v timeout >/dev/null 2>&1; then timeout 0.3 "$@"; else "$@"; fi; }
  git_branch="$(gtimeout git -C "$cwd" --no-optional-locks symbolic-ref --quiet --short HEAD 2>/dev/null)"
  if [ -z "$git_branch" ]; then
    short_sha="$(gtimeout git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)"
    [ -n "$short_sha" ] && git_branch="detached@${short_sha}"
  fi
fi

# --- GitHub PR number for the current branch ---
# `gh pr view` hits the network, far too slow to run per render, so the value
# is served from a per-repo+branch cache and refreshed by a detached background
# fetch at most once per TTL. The timestamp is bumped synchronously before
# spawning so overlapping renders can't stampede duplicate fetches.
pr_number=""
case "$git_branch" in
  "" | detached@*) : ;;
  *)
    if command -v gh >/dev/null 2>&1; then
      repo_top="$(gtimeout git -C "$cwd" --no-optional-locks rev-parse --show-toplevel 2>/dev/null)"
      if [ -n "$repo_top" ]; then
        cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/claude-statusline"
        cache_file="$cache_dir/pr-$(printf '%s|%s' "$repo_top" "$git_branch" | cksum | tr ' \t' '__')"
        now="$(date +%s)"
        cached_at=""; cached_pr=""
        [ -f "$cache_file" ] && IFS=' ' read -r cached_at cached_pr < "$cache_file" 2>/dev/null
        pr_number="${cached_pr:-}"
        if [ $(( now - ${cached_at:-0} )) -ge 600 ]; then
          mkdir -p "$cache_dir" 2>/dev/null
          printf '%s %s\n' "$now" "$pr_number" > "$cache_file" 2>/dev/null
          (
            if command -v timeout >/dev/null 2>&1; then
              pr="$(cd "$repo_top" && timeout 10 gh pr view "$git_branch" --json number -q .number 2>/dev/null)"
            else
              pr="$(cd "$repo_top" && gh pr view "$git_branch" --json number -q .number 2>/dev/null)"
            fi
            printf '%s %s\n' "$(date +%s)" "$pr" > "$cache_file"
          ) >/dev/null 2>&1 &
          disown 2>/dev/null || true
        fi
      fi
    fi
    ;;
esac

if [ -z "$JQ" ]; then
  # No jq on PATH — bare fallback so the bar never breaks.
  fallback="$dir_display"
  if [ -n "$git_branch" ]; then
    fallback+=" ($git_branch"
    [ -n "$pr_number" ] && fallback+=" #$pr_number"
    fallback+=")"
  fi
  printf '%s' "$fallback"
  exit 0
fi

# Extract everything in one jq pass, joined by the ASCII Unit Separator (\x1f).
# A non-whitespace delimiter keeps empty fields in place — IFS-whitespace (tab) would
# collapse adjacent empties and shift every column. Numeric fields floor to int, else "".
IFS=$'\x1f' read -r MODEL CTX_PCT IN_TOK CTX_SIZE FH_PCT FH_RESET WK_PCT WK_RESET <<EOF
$(printf '%s' "$input" | "$JQ" -r '
  def num: if type=="number" then floor else "" end;
  [ (.model.display_name // "?"),
    (.context_window.used_percentage      // "" | num),
    (.context_window.total_input_tokens   // "" | num),
    (.context_window.context_window_size  // "" | num),
    (.rate_limits.five_hour.used_percentage // "" | num),
    (.rate_limits.five_hour.resets_at       // ""),
    (.rate_limits.seven_day.used_percentage // "" | num),
    (.rate_limits.seven_day.resets_at       // "")
  ] | map(tostring) | join("\u001f")')
EOF

# --- most recent user prompt (rendered on a second status line) ---
# Lets you glance at what you last asked after a long-running or resumed session.
# Prefers Claude Code's own `last-prompt` record; falls back to the last genuine
# user message (excluding tool results, meta caveats, and slash-command echoes).
TRANSCRIPT="$(printf '%s' "$input" | "$JQ" -r '.transcript_path // ""')"
PROMPT=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  PROMPT="$("$JQ" -rRn --argjson max 140 '
    reduce inputs as $line ({lp:null, um:null};
      ($line | try fromjson catch null) as $o
      | if ($o | type) != "object" then .
        elif ($o.type=="last-prompt") and ($o.lastPrompt|type=="string") and (($o.lastPrompt|length)>0)
          then .lp = $o.lastPrompt
        elif ($o.type=="user")
             and (($o.isMeta // false) | not)
             and (($o.isSidechain // false) | not)
             and ($o.message.content | type=="string")
             and ($o.message.content | test("^<(command-|local-command-)") | not)
          then .um = $o.message.content
        else . end)
    | (.lp // .um // "")
    | gsub("\\s+"; " ") | sub("^ +"; "") | sub(" +$"; "")
    | if (length > $max) then (.[0:($max-1)] + "…") else . end
  ' "$TRANSCRIPT" 2>/dev/null)"
fi

# --- ANSI colors ---
R=$'\033[0m'; DIM=$'\033[2m'; BOLD=$'\033[1m'
GRN=$'\033[32m'; YEL=$'\033[33m'; RED=$'\033[31m'; CYA=$'\033[36m'
SEP="${DIM}│${R}"

# Color a 0-100 value: <50 green, <80 yellow, else red.
pct_color() { local p=${1:-0}; if [ "$p" -lt 50 ]; then printf '%s' "$GRN"; elif [ "$p" -lt 80 ]; then printf '%s' "$YEL"; else printf '%s' "$RED"; fi; }

# Humanize a token count: 1000000->1M, 230400->230k.
human() {
  local n=${1:-0}
  if   [ "$n" -ge 1000000 ]; then awk -v n="$n" 'BEGIN{printf "%.1fM", n/1000000}';
  elif [ "$n" -ge 1000 ];    then printf '%dk' $((n/1000));
  else printf '%d' "$n"; fi
}

# Compact "time until epoch": 5h-style (Hh Mm) or 7d-style (Dd Hh).
until_short() {
  local target=$1 unit=$2 now rem
  now=$(date +%s); rem=$(( target - now ))
  [ "$rem" -le 0 ] && { printf 'now'; return; }
  if [ "$unit" = day ]; then
    local d=$(( rem/86400 )) h=$(( (rem%86400)/3600 ))
    if [ "$d" -gt 0 ]; then printf '%dd%dh' "$d" "$h"; else printf '%dh' "$h"; fi
  else
    local h=$(( rem/3600 )) m=$(( (rem%3600)/60 ))
    if [ "$h" -gt 0 ]; then printf '%dh%dm' "$h" "$m"; else printf '%dm' "$m"; fi
  fi
}

out="${BOLD}${MODEL}${R}"

# --- directory + git branch (+ PR number) ---
dir_seg="${CYA}${dir_display}${R}"
branch_disp="$git_branch"
[ -n "$pr_number" ] && branch_disp+=" #${pr_number}"
[ -n "$branch_disp" ] && dir_seg+=" ${DIM}(${branch_disp})${R}"
out+=" ${SEP} ${dir_seg}"

# --- context window ---
if [ -n "$CTX_PCT" ]; then
  c=$(pct_color "$CTX_PCT")
  filled=$(( (CTX_PCT + 5) / 10 )); [ "$filled" -gt 10 ] && filled=10
  bar=""; i=0
  while [ "$i" -lt 10 ]; do [ "$i" -lt "$filled" ] && bar+="█" || bar+="░"; i=$((i+1)); done
  seg="${c}ctx ${bar} ${CTX_PCT}%${R}"
  if [ -n "$IN_TOK" ] && [ -n "$CTX_SIZE" ]; then
    seg+=" ${DIM}$(human "$IN_TOK")/$(human "$CTX_SIZE")${R}"
  fi
  out+=" ${SEP} ${seg}"
fi

# --- 5-hour rolling limit (shown as % remaining; colored by % used) ---
if [ -n "$FH_PCT" ]; then
  c=$(pct_color "$FH_PCT"); seg="${c}5h $((100 - FH_PCT))%${R}"
  [ -n "$FH_RESET" ] && seg+=" ${DIM}·$(until_short "$FH_RESET" hour)${R}"
  out+=" ${SEP} ${seg}"
fi

# --- weekly (7-day) limit (shown as % remaining; colored by % used) ---
if [ -n "$WK_PCT" ]; then
  c=$(pct_color "$WK_PCT"); seg="${c}7d $((100 - WK_PCT))%${R}"
  [ -n "$WK_RESET" ] && seg+=" ${DIM}·$(until_short "$WK_RESET" day)${R}"
  out+=" ${SEP} ${seg}"
fi

printf '%s' "$out"

# --- second line: what you last asked ---
[ -n "$PROMPT" ] && printf '\n%s' "${DIM}❯${R} ${PROMPT}"
