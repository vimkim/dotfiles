#!/usr/bin/env bash
# List open CUBRID PRs from teammates and whether vimkim reviewed them.
set -euo pipefail

REPO="CUBRID/cubrid"
REVIEWER="vimkim"
LIMIT=300
INCLUDE_DRAFTS=false

TEAMMATES=(
  hgryoo
  hornetmj
  hyahong
  vimkim
  H2SU
  YeunjunLee
  youngjun9072
  InChiJun
  lht1199
)

usage() {
  cat <<EOF
Usage: $(basename "$0") [--repo OWNER/REPO] [--reviewer LOGIN] [--limit N] [--drafts]

Lists open PRs in the repo authored by the configured CUBRID teammate list, and
shows whether REVIEWER's latest review approved or requested changes.
Draft PRs are hidden by default.

Defaults:
  --repo     $REPO
  --reviewer $REVIEWER
  --limit    $LIMIT

Options:
  --drafts, --include-drafts
             Include draft PRs in the output.
EOF
}

while (($#)); do
  case "$1" in
    --repo)
      REPO="${2:?missing value for --repo}"
      shift 2
      ;;
    --reviewer)
      REVIEWER="${2:?missing value for --reviewer}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:?missing value for --limit}"
      shift 2
      ;;
    --drafts|--include-drafts)
      INCLUDE_DRAFTS=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for cmd in gh jq; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    printf '%s is required but was not found in PATH.\n' "$cmd" >&2
    exit 1
  fi
done

team_json=$(jq -cn '$ARGS.positional' --args "${TEAMMATES[@]}")

prs_json=$(
  gh pr list \
    --repo "$REPO" \
    --state open \
    --limit "$LIMIT" \
    --json number,title,url,author,isDraft,createdAt,latestReviews
)

filtered_json=$(
  jq --argjson teammates "$team_json" --argjson include_drafts "$INCLUDE_DRAFTS" '
    [
      .[]
      | select(.author.login as $author | $teammates | index($author))
      | select($include_drafts or (.isDraft | not))
    ]
    | sort_by(.createdAt)
    | reverse
  ' <<<"$prs_json"
)

count=$(jq 'length' <<<"$filtered_json")

if ((count == 0)); then
  printf 'No open PRs in %s from configured teammates.\n' "$REPO"
  exit 0
fi

printf 'Open PRs in %s from configured teammates\n' "$REPO"
printf 'Reviewer: %s\n\n' "$REVIEWER"
if [[ "$INCLUDE_DRAFTS" != true ]]; then
  printf 'Drafts: hidden (use --drafts to include)\n\n'
fi
printf '%-7s %-13s %-10s %-19s %s\n' "PR" "AUTHOR" "OPENED" "MY REVIEW" "TITLE"
printf '%-7s %-13s %-10s %-19s %s\n' "------" "------------" "----------" "------------------" "-----"

jq -r --arg reviewer "$REVIEWER" '
  def reviewer_latest:
    [(.latestReviews // [])[] | select(.author.login == $reviewer)]
    | sort_by(.submittedAt)
    | last;

  def review_label:
    if .author.login == $reviewer then
      "self-authored"
    else
      reviewer_latest as $review
      | if $review == null then
        "not reviewed"
      elif $review.state == "APPROVED" then
        "APPROVED"
      elif $review.state == "CHANGES_REQUESTED" then
        "CHANGES_REQUESTED"
      else
        "commented only"
      end
    end;

  .[]
  | [
      ("#" + (.number | tostring)),
      .author.login,
      (.createdAt[0:10]),
      review_label,
      ((if .isDraft then "[DRAFT] " else "" end) + .title),
      .url
    ]
  | @tsv
' <<<"$filtered_json" |
while IFS=$'\t' read -r number author opened review title url; do
  printf '%-7s %-13s %-10s %-19s %s\n' "$number" "$author" "$opened" "$review" "$title"
  printf '%-7s %-13s %-10s %-19s %s\n' "" "" "" "" "$url"
done
