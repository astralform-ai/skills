#!/usr/bin/env bash
# resolve-thread.sh <thread_id>
#
# Mark one review thread resolved. GraphQL only — REST has no equivalent, which
# is why replying and resolving are two calls.
#
# `thread_id` is the PRRT_… node id from pr-state.py, not the comment_id.
#
# Resolve only AFTER a marked reply. A resolve without one leaves the reviewer's
# comment newer than yours, so the thread escalates again on the next round and
# the loop spins.

set -euo pipefail

THREAD_ID="${1:?thread_id required (GraphQL node ID, PRRT_…)}"

gh api graphql -f query='
  mutation($id: ID!) {
    resolveReviewThread(input: { threadId: $id }) {
      thread { id isResolved }
    }
  }
' -f id="$THREAD_ID" --jq '.data.resolveReviewThread.thread'
