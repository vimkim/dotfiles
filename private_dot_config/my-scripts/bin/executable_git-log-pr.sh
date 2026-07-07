#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Pretty format (same as gl)
###############################################################################
GIT_PRETTY_FORMAT='%C(auto)%h %C(magenta)%as%C(reset) %C(blue)%an%C(reset)%C(auto)%d %s %C(black)%C(bold)%cr%C(reset)'

###############################################################################
# Default options we always want
###############################################################################
GL_OPS_DEFAULT=(--graph --oneline --color --decorate --date-order)

usage() {
  cat <<'EOF'
glpr - git-log for a GitHub PR base branch and PR head branch only

Usage:
  glpr [<pr-number>|<pr-url>|<branch>] [git-log-options]
  glpr [git-log-options]

Examples:
  glpr
  glpr 123
  glpr 123 -n 80
  glpr --since=2.weeks
EOF
}

die() {
  echo "glpr: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

git_option_requires_value() {
  case "$1" in
    -n|--max-count|--skip|--since|--after|--until|--before|--author|--committer|--grep|--date|--pretty|--format|--decorate|--decorate-refs|--decorate-refs-exclude)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

ref_exists() {
  git rev-parse --verify --quiet "$1^{commit}" >/dev/null
}

rev_oid() {
  git rev-parse --verify "$1^{commit}" 2>/dev/null
}

resolve_ref() {
  local ref
  for ref in "$@"; do
    if [[ -n "$ref" ]] && ref_exists "$ref"; then
      printf '%s\n' "$ref"
      return 0
    fi
  done
  return 1
}

github_repo_from_url() {
  local url="$1"
  local path owner repo

  url="${url%.git}"
  case "$url" in
    git@github.com:*)
      path="${url#git@github.com:}"
      ;;
    ssh://git@github.com/*)
      path="${url#ssh://git@github.com/}"
      ;;
    https://github.com/*)
      path="${url#https://github.com/}"
      ;;
    http://github.com/*)
      path="${url#http://github.com/}"
      ;;
    *)
      return 1
      ;;
  esac

  IFS='/' read -r owner repo _ <<<"${path%/}"
  [[ -n "$owner" && -n "$repo" ]] || return 1

  printf '%s/%s\n' "$owner" "$repo"
}

remote_for_repo() {
  local wanted_repo="$1"
  local remote url repo

  while IFS=$'\t' read -r remote url; do
    repo="$(github_repo_from_url "$url" 2>/dev/null || true)"
    if [[ "$repo" == "$wanted_repo" ]]; then
      printf '%s\n' "$remote"
      return 0
    fi
  done < <(git remote -v | awk '$3 == "(fetch)" { print $1 "\t" $2 }')

  return 1
}

fetch_ref_if_needed() {
  local remote="$1"
  local source_ref="$2"
  local dest_ref="$3"
  local expected_oid="${4:-}"

  [[ -n "$remote" ]] || return 1
  git remote get-url "$remote" >/dev/null 2>&1 || return 1

  if ref_exists "$dest_ref"; then
    if [[ -z "$expected_oid" || "$(rev_oid "$dest_ref")" == "$expected_oid" ]]; then
      return 0
    fi
  fi

  git fetch --quiet "$remote" "+$source_ref:$dest_ref" >/dev/null 2>&1
}

need_cmd git
need_cmd gh

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree"

PR_SELECTOR=""
GL_OPS_EXTRA=()
PATHS=()
EXPECT_OPTION_VALUE=false

while (($#)); do
  arg="$1"
  shift

  if [[ "$EXPECT_OPTION_VALUE" == true ]]; then
    GL_OPS_EXTRA+=("$arg")
    EXPECT_OPTION_VALUE=false
    continue
  fi

  case "$arg" in
    -h|--help)
      usage
      exit 0
      ;;
    --)
      PATHS=("$@")
      break
      ;;
    -*)
      GL_OPS_EXTRA+=("$arg")
      if [[ "$arg" != *=* ]] && git_option_requires_value "$arg"; then
        EXPECT_OPTION_VALUE=true
      fi
      ;;
    *)
      if [[ -n "$PR_SELECTOR" ]]; then
        die "expected only one PR selector, got: $PR_SELECTOR and $arg"
      fi
      PR_SELECTOR="$arg"
      ;;
  esac
done

[[ "$EXPECT_OPTION_VALUE" == false ]] || die "missing value for git log option"

GH_PR_ARGS=()
if [[ -n "$PR_SELECTOR" ]]; then
  GH_PR_ARGS+=("$PR_SELECTOR")
fi

PR_METADATA="$(
  gh pr view "${GH_PR_ARGS[@]}" \
    --json baseRefName,headRefName,baseRefOid,headRefOid,headRepository,number,url \
    --jq '[.baseRefName, .headRefName, .baseRefOid, .headRefOid, .url, (.headRepository.nameWithOwner // ""), (.number | tostring)] | @tsv'
)" || die "failed to read PR metadata with gh"

IFS=$'\t' read -r BASE_REF_NAME HEAD_REF_NAME BASE_REF_OID HEAD_REF_OID PR_URL HEAD_REPO PR_NUMBER <<<"$PR_METADATA"

[[ -n "$BASE_REF_NAME" ]] || die "PR metadata did not include baseRefName"
[[ -n "$HEAD_REF_NAME" ]] || die "PR metadata did not include headRefName"
[[ -n "$BASE_REF_OID" ]] || die "PR metadata did not include baseRefOid"
[[ -n "$HEAD_REF_OID" ]] || die "PR metadata did not include headRefOid"
[[ -n "$PR_URL" ]] || die "PR metadata did not include url"
[[ -n "$PR_NUMBER" ]] || die "PR metadata did not include number"

BASE_REPO="$(github_repo_from_url "$PR_URL")" || die "could not parse base repository from PR URL: $PR_URL"

BASE_REMOTE="$(remote_for_repo "$BASE_REPO" || true)"
if [[ -z "$BASE_REMOTE" ]] && git remote get-url origin >/dev/null 2>&1; then
  BASE_REMOTE="origin"
fi

BASE_REMOTE_REF=""
HEAD_PR_REF=""

if [[ -n "$BASE_REMOTE" ]]; then
  BASE_REMOTE_REF="refs/remotes/$BASE_REMOTE/$BASE_REF_NAME"
  HEAD_PR_REF="refs/remotes/$BASE_REMOTE/pr/$PR_NUMBER"

  fetch_ref_if_needed "$BASE_REMOTE" "refs/heads/$BASE_REF_NAME" "$BASE_REMOTE_REF" "$BASE_REF_OID" || true
  fetch_ref_if_needed "$BASE_REMOTE" "refs/pull/$PR_NUMBER/head" "$HEAD_PR_REF" "$HEAD_REF_OID" || true
fi

HEAD_REMOTE_REF=""
if [[ "$HEAD_REPO" == "$BASE_REPO" && -n "$BASE_REMOTE" ]]; then
  HEAD_REMOTE_REF="refs/remotes/$BASE_REMOTE/$HEAD_REF_NAME"
  fetch_ref_if_needed "$BASE_REMOTE" "refs/heads/$HEAD_REF_NAME" "$HEAD_REMOTE_REF" "$HEAD_REF_OID" || true
fi

BASE_REV="$(
  resolve_ref \
    "$BASE_REMOTE_REF" \
    "refs/heads/$BASE_REF_NAME" \
    "$BASE_REF_OID"
)" || die "could not resolve PR base branch '$BASE_REF_NAME' ($BASE_REF_OID)"

HEAD_REV="$(
  resolve_ref \
    "$HEAD_PR_REF" \
    "$HEAD_REMOTE_REF" \
    "refs/heads/$HEAD_REF_NAME" \
    "$HEAD_REF_OID"
)" || die "could not resolve PR head branch '$HEAD_REF_NAME' ($HEAD_REF_OID)"

GIT_LOG_REVS=("$BASE_REV" "$HEAD_REV")
if ((${#PATHS[@]})); then
  GIT_LOG_REVS+=("--" "${PATHS[@]}")
fi

GIT_PAGER="less -iRFSX" \
git log \
  "${GL_OPS_DEFAULT[@]}" \
  "${GL_OPS_EXTRA[@]}" \
  --pretty=format:"$GIT_PRETTY_FORMAT" \
  "${GIT_LOG_REVS[@]}"
