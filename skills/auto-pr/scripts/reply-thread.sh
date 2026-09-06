#!/usr/bin/env bash
# reply-thread.sh <PR#> <comment_id> <body>
#
# Reply to one inline review comment:
#   POST /repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies
#
# `comment_id` is the integer `databaseId` that pr-state.py reports per thread —
# NOT the GraphQL node ID and NOT the thread_id. pr-state.py points it at the
# LATEST reviewer comment, so the reply lands under the remark you are answering.
#
# Replying does NOT resolve the thread. Run scripts/resolve-thread.sh after —
# resolve is GraphQL-only, REST has no equivalent.
#
# Your reply body MUST end with a marker: <!-- auto-pr:fixed|nit|wrong -->.
# The gate reads it back to make the classification durable; without one the
# thread re-derives as unclassified on every round and the loop never converges.
#
# Uses gh's built-in --jq (gojq). Do NOT reach for `jq`: it is not installed in
# this sandbox.

set -euo pipefail

PR="${1:?PR number required}"
COMMENT_ID="${2:?inline comment_id (databaseId integer) required}"
BODY="${3:?reply body required}"

REPO="$(gh pr view "$PR" --json url \
  --jq '.url | capture("github.com/(?<o>[^/]+)/(?<r>[^/]+)/") | "\(.o)/\(.r)"')"

gh api -X POST \
  "repos/$REPO/pulls/$PR/comments/$COMMENT_ID/replies" \
  -f body="$BODY" \
  --jq '{id: .id, url: .html_url, author: .user.login}'
