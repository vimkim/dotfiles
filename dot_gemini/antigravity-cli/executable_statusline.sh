#!/usr/bin/env bash
# Antigravity CLI (agy) status line — built from agy's session JSON payload on
# stdin (schema: https://antigravity.google/docs/cli/statusline).
#
# Shows: model (+ execution mode + bypass indicator), current directory + git
# branch (+ GitHub PR number), context window usage/size, quota/rate-limit
# remaining + reset time (excluding unused 3p-5h and 3p-7d), and active
# subagent/background task counts when nonzero.
#
# Kept fast/non-blocking: single jq pass over stdin, cheap read-only git
# metadata calls with --no-optional-locks, and cached background `gh pr view`.

set -uo pipefail

input="$(cat)"

# --- locate jq and gh robustly (statusLine runs via `sh -c`, often with minimal PATH) ---
find_bin() {
  local name=$1 found cand
  found="$(command -v "$name" 2>/dev/null || true)"
  for cand in "/home/linuxbrew/.linuxbrew/bin/$name" "/usr/bin/$name" "/usr/local/bin/$name" "/opt/homebrew/bin/$name"; do
    [ -n "$found" ] && break
    [ -x "$cand" ] && found="$cand"
  done
  printf '%s' "$found"
}

JQ="$(find_bin jq)"
GH="$(find_bin gh)"

# --- working directory for this session ---
cwd="$PWD"
if [ -n "$JQ" ]; then
  extracted="$(printf '%s' "$input" | "$JQ" -r '.workspace.current_dir // .cwd // empty' 2>/dev/null || true)"
  [ -n "$extracted" ] && cwd="$extracted"
fi

# --- directory (full path, ~ shortened) + git branch ---
dir_display="$cwd"
case "$dir_display" in
  "$HOME") dir_display="~" ;;
  "$HOME"/*) dir_display="~${dir_display#"$HOME"}" ;;
esac

gtimeout() { if command -v timeout >/dev/null 2>&1; then timeout 0.3 "$@"; else "$@"; fi; }

git_branch=""
if command -v git >/dev/null 2>&1 && [ -d "$cwd" ]; then
  git_branch="$(gtimeout git -C "$cwd" --no-optional-locks symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [ -z "$git_branch" ]; then
    short_sha="$(gtimeout git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null || true)"
    [ -n "$short_sha" ] && git_branch="detached@${short_sha}"
  fi
fi

# --- GitHub PR number for the current branch (cached, detached background refresh) ---
pr_number=""
case "$git_branch" in
  "" | detached@*) : ;;
  *)
    if [ -n "$GH" ] && [ -d "$cwd" ]; then
      repo_top="$(gtimeout git -C "$cwd" --no-optional-locks rev-parse --show-toplevel 2>/dev/null || true)"
      if [ -n "$repo_top" ]; then
        cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/agy-statusline"
        cache_file="$cache_dir/pr-$(printf '%s|%s' "$repo_top" "$git_branch" | cksum | tr ' \t' '__')"
        now="$(date +%s)"
        cached_at=""
        cached_pr=""
        if [ -f "$cache_file" ]; then
          IFS=' ' read -r cached_at cached_pr < "$cache_file" 2>/dev/null || true
        fi
        pr_number="${cached_pr:-}"
        if [ $(( now - ${cached_at:-0} )) -ge 600 ]; then
          mkdir -p "$cache_dir" 2>/dev/null || true
          printf '%s %s\n' "$now" "$pr_number" > "$cache_file" 2>/dev/null || true
          (
            if command -v timeout >/dev/null 2>&1; then
              pr="$(cd "$repo_top" && timeout 10 "$GH" pr view "$git_branch" --json number -q .number 2>/dev/null || true)"
            else
              pr="$(cd "$repo_top" && "$GH" pr view "$git_branch" --json number -q .number 2>/dev/null || true)"
            fi
            printf '%s %s\n' "$(date +%s)" "$pr" > "$cache_file" 2>/dev/null || true
          ) </dev/null >/dev/null 2>&1 &
          disown 2>/dev/null || true
        fi
      fi
    fi
    ;;
esac

if [ -z "$JQ" ]; then
  fallback="$dir_display"
  if [ -n "$git_branch" ]; then
    fallback+=" ($git_branch"
    [ -n "$pr_number" ] && fallback+=" #$pr_number"
    fallback+=")"
  fi
  printf '%s' "$fallback"
  exit 0
fi

# --- extract all fields in one jq pass ---
# Line 1: scalar fields joined by \x1f (ASCII Unit Separator).
# Lines 2+: quota buckets sorted by reset window (ascending) then key:
#   label \x1f kind(frac|amt) \x1f value \x1f reset_in_seconds
# shellcheck disable=SC2016
jq_out="$(printf '%s' "$input" | "$JQ" -r '
  def num_floor: if type == "number" then floor else "" end;
  def pos_int: if type == "number" and . > 0 then floor else "" end;
  def clamp_pct: if . < 0 then 0 elif . > 100 then 100 else . end;
  def short_bucket:
    gsub("-weekly$"; "-7d")
    | gsub("weekly"; "7d")
    | gsub("five[-_]?hour"; "5h")
    | gsub("5[-_]?hour"; "5h");

  (.context_window.context_window_size // 0) as $ctx_size
  | (.context_window.used_percentage) as $used_pct_raw
  | (if ($used_pct_raw | type) == "number" then ($used_pct_raw | floor | clamp_pct) else "" end) as $ctx_pct
  | (if ($ctx_size | type) == "number" and $ctx_size > 0 and ($used_pct_raw | type) == "number"
     then (($ctx_size * $used_pct_raw / 100) | floor)
     elif (.context_window.total_input_tokens | type) == "number"
     then (.context_window.total_input_tokens | floor)
     else "" end) as $used_tok
  | ([(.subagents // [])[] | select(.status == "running")] | length) as $run_ag
  | ([
      (.model.display_name // .model.id // "?"),
      (.model.effort // ""),
      (.cycle_mode // ""),
      $ctx_pct,
      $used_tok,
      ($ctx_size | pos_int),
      $run_ag,
      (.task_count // 0 | num_floor)
    ] | map(tostring) | join("\u001f")),
    (
      (.quota // {})
      | to_entries
      | map(select(
          (.value | type) == "object"
          and ((.value.disabled // false) | not)
          and (((.key | short_bucket) | test("^3p-(5h|7d)$")) | not)
        ))
      | sort_by([((.value.reset_in_seconds // 999999999) | if type == "number" then . else 999999999 end), .key])
      | .[]
      | if (.value.remaining_fraction | type) == "number" then
          [(.key | short_bucket), "frac", ((.value.remaining_fraction * 100) | round | clamp_pct), (.value.reset_in_seconds | pos_int)]
        elif (.value.remaining_amount | type) == "number" then
          [(.key | short_bucket), "amt", (.value.remaining_amount | floor), (.value.reset_in_seconds | pos_int)]
        else empty end
      | map(tostring) | join("\u001f")
    )
' 2>/dev/null || true)"

MODEL="?"
EFFORT=""
MODE=""
CTX_PCT=""
USED_TOK=""
CTX_SIZE=""
RUN_AG="0"
TASK_COUNT="0"
QUOTA_LINES=()

line_idx=0
while IFS= read -r line; do
  if [ "$line_idx" -eq 0 ]; then
    IFS=$'\x1f' read -r MODEL EFFORT MODE CTX_PCT USED_TOK CTX_SIZE RUN_AG TASK_COUNT <<< "$line"
  elif [ -n "$line" ]; then
    QUOTA_LINES+=("$line")
  fi
  line_idx=$((line_idx + 1))
done <<< "$jq_out"

# --- ANSI colors ---
R=$'\033[0m'; DIM=$'\033[2m'; BOLD=$'\033[1m'
GRN=$'\033[32m'; YEL=$'\033[33m'; RED=$'\033[31m'; CYA=$'\033[36m'
SEP="${DIM}│${R}"

# Color a 0-100 usage value: <50 green, <80 yellow, else red.
pct_color() {
  local p=${1:-0}
  if [ "$p" -lt 50 ]; then printf '%s' "$GRN"
  elif [ "$p" -lt 80 ]; then printf '%s' "$YEL"
  else printf '%s' "$RED"
  fi
}

# Humanize a token count: 1048576->1.0M, 149317->149k.
human() {
  local n=${1:-0}
  if   [ "$n" -ge 1000000 ]; then LC_NUMERIC=C awk -v n="$n" 'BEGIN{printf "%.1fM", n/1000000}'
  elif [ "$n" -ge 1000 ];    then printf '%dk' $((n / 1000))
  else printf '%d' "$n"
  fi
}

# Compact countdown from seconds: >=1d -> DdHh, >=1h -> HhMm, else Mm.
dur_short() {
  local rem=${1:-0}
  if [ "$rem" -le 0 ]; then
    printf 'now'
    return
  fi
  if [ "$rem" -ge 86400 ]; then
    local d=$((rem / 86400)) h=$(((rem % 86400) / 3600))
    if [ "$h" -gt 0 ]; then printf '%dd%dh' "$d" "$h"; else printf '%dd' "$d"; fi
  elif [ "$rem" -ge 3600 ]; then
    local h=$((rem / 3600)) m=$(((rem % 3600) / 60))
    if [ "$m" -gt 0 ]; then printf '%dh%dm' "$h" "$m"; else printf '%dh' "$h"; fi
  else
    local m=$((rem / 60))
    [ "$m" -lt 1 ] && m=1
    printf '%dm' "$m"
  fi
}

# Detect whether the invoking `agy` process was launched with
# `--dangerously-skip-permissions`. `agy` runs statusLine directly or via
# `sh -c`, so inspect only the parent (and grandparent if parent is a shell).
detect_bypass() {
  local pid=$PPID depth=0 cmd_base arg ppid stat_line stat_rest ps_line ps_args
  local -a args=()
  while [ "$depth" -lt 2 ] && [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null; do
    args=()
    ppid=""
    if [ -r "/proc/$pid/cmdline" ] && [ -r "/proc/$pid/stat" ]; then
      while IFS= read -r -d '' arg || [ -n "$arg" ]; do
        args+=("$arg")
      done < "/proc/$pid/cmdline"
      IFS= read -r stat_line < "/proc/$pid/stat" || true
      stat_rest="${stat_line##*) }"
      read -r _ ppid _ <<< "$stat_rest"
    elif command -v ps >/dev/null 2>&1; then
      ps_line="$(ps -o ppid=,args= -p "$pid" 2>/dev/null || true)"
      read -r ppid ps_args <<< "$ps_line"
      if [ -n "$ps_args" ]; then
        read -r -a args <<< "$ps_args"
      fi
    else
      break
    fi

    [ "${#args[@]}" -gt 0 ] || break
    cmd_base="${args[0]##*/}"
    cmd_base="${cmd_base#-}"
    if [ "$cmd_base" = "agy" ]; then
      for arg in "${args[@]:1}"; do
        if [ "$arg" = "--dangerously-skip-permissions" ]; then
          printf '1'
          return 0
        fi
      done
      return 0
    fi

    case "$cmd_base" in
      sh|bash|dash|zsh)
        pid="$ppid"
        depth=$((depth + 1))
        ;;
      *)
        break
        ;;
    esac
  done
}

# --- model (+ effort if not already in display_name, + cycle_mode) ---
model_disp="$MODEL"
if [ -n "$EFFORT" ]; then
  model_lower="${MODEL,,}"
  effort_lower="${EFFORT,,}"
  case "$model_lower" in
    *"$effort_lower"*) : ;;
    *) model_disp+=" (${EFFORT})" ;;
  esac
fi

out="${BOLD}${model_disp}${R}"
case "$MODE" in
  plan)         out+=" ${YEL}[plan]${R}" ;;
  auto)         out+=" ${GRN}[auto]${R}" ;;
  accept-edits) out+=" ${CYA}[edits]${R}" ;;
  "")           : ;;
  *)            out+=" ${DIM}[${MODE}]${R}" ;;
esac

BYPASS="$(detect_bypass)"
if [ "${BYPASS:-0}" = "1" ]; then
  out+=" ${RED}[bypass]${R}"
fi

# --- directory + git branch (+ PR number) ---
dir_seg="${CYA}${dir_display}${R}"
branch_disp="$git_branch"
[ -n "$pr_number" ] && branch_disp+=" #${pr_number}"
[ -n "$branch_disp" ] && dir_seg+=" ${DIM}(${branch_disp})${R}"
out+=" ${SEP} ${dir_seg}"

# --- context window ---
if [ -n "$CTX_PCT" ]; then
  c="$(pct_color "$CTX_PCT")"
  filled=$(( (CTX_PCT + 5) / 10 ))
  [ "$filled" -gt 10 ] && filled=10
  bar=""
  i=0
  while [ "$i" -lt 10 ]; do
    [ "$i" -lt "$filled" ] && bar+="█" || bar+="░"
    i=$((i + 1))
  done
  seg="${c}ctx ${bar} ${CTX_PCT}%${R}"
  if [ -n "$USED_TOK" ] && [ -n "$CTX_SIZE" ]; then
    seg+=" ${DIM}$(human "$USED_TOK")/$(human "$CTX_SIZE")${R}"
  fi
  out+=" ${SEP} ${seg}"
elif [ -n "$CTX_SIZE" ]; then
  out+=" ${SEP} ${GRN}ctx ░░░░░░░░░░ 0%${R} ${DIM}0/$(human "$CTX_SIZE")${R}"
fi

# --- quota / rate limits (shown as % remaining; colored by % used) ---
low_quota=0
for qline in "${QUOTA_LINES[@]}"; do
  IFS=$'\x1f' read -r q_label q_kind q_val q_reset <<< "$qline"
  [ -z "$q_label" ] && continue
  if [ "$q_kind" = "frac" ]; then
    used_pct=$((100 - q_val))
    c="$(pct_color "$used_pct")"
    seg="${c}${q_label} ${q_val}%${R}"
    [ "$q_val" -lt 10 ] && low_quota=1
  else
    seg="${CYA}${q_label} ${q_val}${R}"
  fi
  if [ -n "$q_reset" ]; then
    seg+=" ${DIM}·$(dur_short "$q_reset")${R}"
  fi
  out+=" ${SEP} ${seg}"
done

if [ "$low_quota" -eq 1 ]; then
  out+=" ${SEP} ${RED}Low quota (<10%)${R}"
fi

# --- active subagents / background tasks (only when nonzero) ---
act=()
[ "${RUN_AG:-0}" -gt 0 ] && act+=("${RUN_AG}ag")
[ "${TASK_COUNT:-0}" -gt 0 ] && act+=("${TASK_COUNT}bg")
if [ "${#act[@]}" -gt 0 ]; then
  out+=" ${SEP} ${DIM}${act[*]}${R}"
fi

printf '%s' "$out"
