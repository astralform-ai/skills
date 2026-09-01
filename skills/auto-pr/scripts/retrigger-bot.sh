#!/usr/bin/env bash
# retrigger-bot.sh <PR#> <bot-name> [<focus-comment-body>]
#
# Posts a focused @mention from the user's gh account to re-trigger a reviewer bot.
# This is for bots that don't auto-fire on push (Copilot, sometimes Claude on
# repos without the hardened workflow). Bots that auto-fire on push (CodeQL)
# don't need this — push handles them.
#
# Usage:
#   retrigger-bot.sh 123 claude
#   retrigger-bot.sh 123 claude "Re-review focusing on the new edge case in foo.ts:42"
#   retrigger-bot.sh 123 copilot
#
# Why a focused body: a bare "@claude please re-review" is noisy. Naming what you
# addressed and what you want a second look at gives the reviewer signal.

set -euo pipefail

PR="${1:?PR number required}"
BOT="${2:?bot name required: claude | copilot}"
FOCUS="${3:-}"

# Map shorthand to mention handle. Some bots respond only to a specific handle;
# Copilot is re-requested via review-request API instead of @mention.
case "$BOT" in
  claude)
    HANDLE="@claude"
    ;;
  copilot)
    # Copilot uses review-requests, not mentions. Switch to that path.
    REPO="$(gh pr view "$PR" --json headRepository,url --jq '.url | capture("github.com/(?<o>[^/]+)/(?<r>[^/]+)/") | "\(.o)/\(.r)"')"
    gh api -X POST "repos/$REPO/pulls/$PR/requested_reviewers" \
      -f 'reviewers[]=copilot-pull-request-reviewer[bot]' 2>/dev/null \
      || gh api -X POST "repos/$REPO/pulls/$PR/requested_reviewers" \
           -f 'reviewers[]=copilot-pull-request-reviewer'
    echo "{\"action\":\"copilot_review_requested\",\"pr\":$PR}"
    exit 0
    ;;
  *)
    echo "Unknown bot: $BOT (supported: claude, copilot)" >&2
    exit 2
    ;;
esac

if [ -n "$FOCUS" ]; then
  BODY="$HANDLE please re-review the latest commit. $FOCUS"
else
  BODY="$HANDLE please re-review the latest commit. Addressed prior feedback."
fi

gh pr comment "$PR" --body "$BODY"
echo "{\"action\":\"mention_posted\",\"pr\":$PR,\"handle\":\"$HANDLE\"}"
