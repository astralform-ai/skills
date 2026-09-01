#!/usr/bin/env bash
# reply-thread.sh <PR#> <comment_id> <body>
#
# Replies to a specific inline review comment via the REST endpoint:
#   POST /repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies
#
# REST is one of two valid reply paths. The GraphQL equivalent is:
#   addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $tid, body: ...})
# Use whichever matches the ID you already have. This script defaults to REST
# because list-unresolved-threads.sh surfaces both `comment_id` (integer
# `databaseId`, REST) and `thread_id` (PRRT_ node ID, GraphQL).
#
# Whichever reply API you use, you STILL need scripts/resolve-thread.sh after.
# Reply does not mark the thread resolved on its own — resolve must go through
# GraphQL (REST has no resolveReviewThread equivalent).
#
# Usage:
#   reply-thread.sh 123 1234567890 "Applied in <sha> — narrowed cycle check to direct refs."
#   reply-thread.sh 123 1234567890 "Declining — actions/checkout@v6 exists (release URL). CI green."
#
# `comment_id` is the integer `databaseId` from list-unresolved-threads.sh,
# NOT the GraphQL node ID and NOT the thread_id.

set -euo pipefail

PR="${1:?PR number required}"
COMMENT_ID="${2:?inline comment_id (databaseId integer) required}"
BODY="${3:?reply body required}"

REPO="$(gh pr view "$PR" --json url --jq '.url | capture("github.com/(?<o>[^/]+)/(?<r>[^/]+)/") | "\(.o)/\(.r)"')"

gh api -X POST \
  "repos/$REPO/pulls/$PR/comments/$COMMENT_ID/replies" \
  -f body="$BODY" \
  | jq '{id, url: .html_url, author: .user.login}'
