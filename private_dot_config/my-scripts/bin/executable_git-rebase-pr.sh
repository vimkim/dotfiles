#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
grbpr - rebase a GitHub PR head branch onto its base branch

Usage:
  grbpr [<pr-number>|<pr-url>|<branch>]

Examples:
  grbpr
  grbpr 123
EOF
}

die() {
  echo "grbpr: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

ref_exists() {
  git rev-parse --verify --quiet "$1^{commit}" >/dev/null
}

rev_oid() {
  git rev-parse --verify "$1^{commit}" 2>/dev/null
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
  local source="$1"
  local source_ref="$2"
  local dest_ref="$3"
  local expected_oid="${4:-}"

  if ref_exists "$dest_ref"; then
    if [[ -z "$expected_oid" || "$(rev_oid "$dest_ref")" == "$expected_oid" ]]; then
      return 0
    fi
  fi

  git fetch --quiet "$source" "+$source_ref:$dest_ref" >/dev/null 2>&1
}

confirm() {
  local answer

  if [[ -r /dev/tty && -w /dev/tty ]]; then
    printf 'Proceed? [y/N] ' >/dev/tty
    read -r answer </dev/tty || answer=""
  else
    printf 'Proceed? [y/N] '
    read -r answer || answer=""
  fi

  case "$answer" in
    y|Y)
      return 0
      ;;
    *)
      echo "Cancelled."
      exit 1
      ;;
  esac
}

need_clean_worktree() {
  git update-index -q --refresh
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    die "worktree has tracked uncommitted changes; commit or stash them first"
  fi
}

need_no_rebase_in_progress() {
  local rebase_merge rebase_apply

  rebase_merge="$(git rev-parse --git-path rebase-merge)"
  rebase_apply="$(git rev-parse --git-path rebase-apply)"

  if [[ -d "$rebase_merge" || -d "$rebase_apply" ]]; then
    die "a rebase is already in progress"
  fi
}

need_cmd git
need_cmd gh

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree"

PR_SELECTOR=""
while (($#)); do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      if [[ -n "$PR_SELECTOR" ]]; then
        die "expected only one PR selector, got: $PR_SELECTOR and $1"
      fi
      PR_SELECTOR="$1"
      ;;
  esac
  shift
done

if (($#)); then
  die "unexpected argument(s): $*"
fi

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
BASE_SOURCE=""
BASE_LOCAL_REF=""

if [[ -n "$BASE_REMOTE" ]]; then
  BASE_SOURCE="$BASE_REMOTE"
  BASE_LOCAL_REF="refs/remotes/$BASE_REMOTE/$BASE_REF_NAME"
else
  BASE_SOURCE="https://github.com/$BASE_REPO.git"
  BASE_LOCAL_REF="refs/grbpr-base/$BASE_REPO/$BASE_REF_NAME"
fi

CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD || true)"
[[ -n "$CURRENT_BRANCH" ]] || die "detached HEAD; check out the PR branch first"

LOCAL_HEAD_BRANCH=""
WILL_SWITCH=false
if [[ "$CURRENT_BRANCH" == "$HEAD_REF_NAME" ]]; then
  LOCAL_HEAD_BRANCH="$CURRENT_BRANCH"
elif git show-ref --verify --quiet "refs/heads/$HEAD_REF_NAME"; then
  LOCAL_HEAD_BRANCH="$HEAD_REF_NAME"
  WILL_SWITCH=true
else
  die "local PR head branch '$HEAD_REF_NAME' was not found; check it out first"
fi

need_no_rebase_in_progress
need_clean_worktree

cat <<EOF
PR #$PR_NUMBER
  url:     $PR_URL
  base:    $BASE_REPO:$BASE_REF_NAME ($BASE_REF_OID)
  head:    ${HEAD_REPO:-unknown}:$HEAD_REF_NAME ($HEAD_REF_OID)
  current: $CURRENT_BRANCH
EOF

if [[ "$WILL_SWITCH" == true ]]; then
  echo "  switch:  git switch $LOCAL_HEAD_BRANCH"
fi

cat <<EOF

This will run:
  git fetch $BASE_SOURCE +refs/heads/$BASE_REF_NAME:$BASE_LOCAL_REF
  git rebase $BASE_LOCAL_REF
EOF

confirm

fetch_ref_if_needed "$BASE_SOURCE" "refs/heads/$BASE_REF_NAME" "$BASE_LOCAL_REF" "$BASE_REF_OID" \
  || die "failed to fetch base branch '$BASE_REF_NAME' from '$BASE_SOURCE'"

BASE_REV="$BASE_LOCAL_REF"
if ! ref_exists "$BASE_REV"; then
  BASE_REV="$BASE_REF_OID"
fi
ref_exists "$BASE_REV" || die "could not resolve PR base branch '$BASE_REF_NAME' ($BASE_REF_OID)"

if [[ "$WILL_SWITCH" == true ]]; then
  git switch "$LOCAL_HEAD_BRANCH"
fi

git rebase "$BASE_REV"
