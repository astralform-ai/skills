#!/usr/bin/env bash
# resolve-thread.sh <thread_id>
#
# Marks a single review thread as resolved via GraphQL.
# Use ONLY after you've materially answered the thread (fix or evidence-based reply).

set -euo pipefail

THREAD_ID="${1:?thread_id required (GraphQL node ID)}"

gh api graphql -f query='
  mutation($id: ID!) {
    resolveReviewThread(input: { threadId: $id }) {
      thread { id isResolved }
    }
  }
' -f id="$THREAD_ID" \
  | jq '.data.resolveReviewThread.thread'
