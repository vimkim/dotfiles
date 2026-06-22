#!/usr/bin/env bash
# Claude Code status line — native, dependency-light (needs jq).
# Shows: model · context-window usage · 5-hour limit · weekly (7-day) limit · session cost.
# Reads the session JSON on stdin (schema: https://code.claude.com/docs/en/statusline).
#
# rate_limits.* only appear for Claude.ai Pro/Max accounts, and only after the first
# API response of a session — so those segments are hidden until the data exists.

set -uo pipefail

# --- locate jq robustly (statusline runs with a minimal PATH on some setups) ---
JQ="$(command -v jq 2>/dev/null)"
for cand in /home/linuxbrew/.linuxbrew/bin/jq /usr/bin/jq /usr/local/bin/jq /opt/homebrew/bin/jq; do
  [ -n "$JQ" ] && break
  [ -x "$cand" ] && JQ="$cand"
done

input="$(cat)"

# Fall back to a bare line if jq is unavailable, so the bar never breaks.
if [ -z "$JQ" ]; then
  printf '%s' "$(printf '%s' "$input" | grep -o '"display_name"[^,]*' | head -1 | sed 's/.*: *"//;s/"//')"
  exit 0
fi

# Extract everything in one jq pass, joined by the ASCII Unit Separator (\x1f).
# A non-whitespace delimiter keeps empty fields in place — IFS-whitespace (tab) would
# collapse adjacent empties and shift every column. Numeric fields floor to int, else "".
IFS=$'\x1f' read -r MODEL CTX_PCT IN_TOK CTX_SIZE COST FH_PCT FH_RESET WK_PCT WK_RESET <<EOF
$(printf '%s' "$input" | "$JQ" -r '
  def num: if type=="number" then floor else "" end;
  [ (.model.display_name // "?"),
    (.context_window.used_percentage      // "" | num),
    (.context_window.total_input_tokens   // "" | num),
    (.context_window.context_window_size  // "" | num),
    (.cost.total_cost_usd // 0),
    (.rate_limits.five_hour.used_percentage // "" | num),
    (.rate_limits.five_hour.resets_at       // ""),
    (.rate_limits.seven_day.used_percentage // "" | num),
    (.rate_limits.seven_day.resets_at       // "")
  ] | map(tostring) | join("\u001f")')
EOF

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

# --- 5-hour rolling limit ---
if [ -n "$FH_PCT" ]; then
  c=$(pct_color "$FH_PCT"); seg="${c}5h ${FH_PCT}%${R}"
  [ -n "$FH_RESET" ] && seg+=" ${DIM}·$(until_short "$FH_RESET" hour)${R}"
  out+=" ${SEP} ${seg}"
fi

# --- weekly (7-day) limit ---
if [ -n "$WK_PCT" ]; then
  c=$(pct_color "$WK_PCT"); seg="${c}7d ${WK_PCT}%${R}"
  [ -n "$WK_RESET" ] && seg+=" ${DIM}·$(until_short "$WK_RESET" day)${R}"
  out+=" ${SEP} ${seg}"
fi

# --- session cost ---
out+=" ${SEP} ${CYA}\$$(awk -v c="${COST:-0}" 'BEGIN{printf "%.2f", c}')${R}"

printf '%s' "$out"
