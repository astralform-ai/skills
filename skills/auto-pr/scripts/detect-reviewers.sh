#!/usr/bin/env bash
# detect-reviewers.sh <PR#>
#
# Returns a JSON profile of which reviewers are on the PR and whether each has
# signaled approval via its OWN mechanism. Critical: neither Claude nor Copilot
# ever submits GitHub's formal APPROVED state — they only emit COMMENTED.
# Approval is detected per-bot:
#
#   claude[bot]                    no reliable structural signal; layered
#                                  heuristic — positive-signal-first, then
#                                  blocker scan with negation-context stripping
#   copilot-pull-request-reviewer  latest review is anchored to the PR's current
#                                  head SHA (review.commit_id == head.sha) and
#                                  Copilot has 0 inline comments anchored to
#                                  that commit
#   github-advanced-security[bot]  ALL CodeQL check-runs on head commit are
#                                  conclusion=success (or no CodeQL ran)
#   any other [bot]                fallback: state == APPROVED only
#   humans                         state == APPROVED OR CHANGES_REQUESTED
#
# Honors GH_REPO env var or current cwd's gh-resolved repo for cross-repo use.
#
# Output schema:
# {
#   "pr_number": <int>,
#   "pr_author": "<login>",
#   "reviewers": {
#     "<login>": {
#       "kind": "bot|human",
#       "last_review_state": "APPROVED|CHANGES_REQUESTED|COMMENTED|null",
#       "is_approved": true|false,
#       "approval_source": "<adapter name explaining why>"
#     }
#   },
#   "all_bots_approved": bool,
#   "reviews_seen": bool,
#   "any_changes_requested": bool,
#   "bots_pending_signoff": [<login>...],   // bots in COMMENTED state with no approval signal yet
#   "humans": [<login>...],
#   "bots": [<login>...]
# }

set -euo pipefail

PR="${1:?PR number required}"

# Owner/repo from gh's repo-resolution. Honors GH_REPO env or current repo.
repo_data="$(gh pr view "$PR" --json url,reviews,author 2>/dev/null)"
owner_repo="$(echo "$repo_data" | jq -r '.url | capture("github.com/(?<o>[^/]+)/(?<r>[^/]+)/") | "\(.o)/\(.r)"')"
pr_author="$(echo "$repo_data" | jq -r '.author.login // ""')"

# Bot detection rule. GitHub returns app logins with [bot] suffix in some
# surfaces and without it in others — match either way.
is_bot_login() {
  local login="$1"
  case "$login" in
    *"[bot]") return 0 ;;
    claude|copilot-pull-request-reviewer|github-advanced-security|dependabot|renovate|sentry-io)
      return 0 ;;
    *) return 1 ;;
  esac
}

# Adapter: Claude. No reliable structural signal. Execution order:
#   1. Strip negated positives with a tolerant window (over-stripping fails
#      closed) and negated blockers with an adjacent-only window (over-stripping
#      a blocker would fail open).
#   2. Positive signals on the cleaned body.
#   3. Blocker keywords on the cleaned body.
#   4. Ambiguous default = false.
#
# The body lookup uses --slurp so multi-page comment streams resolve to a
# single canonical "latest" via timestamp sort, not per-page last.
claude_is_approved() {
  local body
  body="$(gh api "repos/$owner_repo/issues/$PR/comments" --paginate --slurp \
    | jq -r '[.[][]] | sort_by(.created_at) | map(select(.user.login == "claude[bot]")) | last | .body // ""')"
  [ -z "$body" ] && return 1

  # Strip negated positives with a tolerant window, then negated blockers
  # adjacent-only. The asymmetry is load-bearing: over-stripping a positive
  # fails closed, over-stripping a blocker fails open.
  # Use perl (not sed): BSD sed on macOS doesn't support `\b` word boundaries.
  # Perl 5 is on macOS by default and standard on Linux GitHub Actions runners.
  local cleaned
  cleaned="$(echo "$body" | perl -pe 's/(\b(not|no|never|cannot|unable|needs? to be)|[a-z]+n.t)\b[^.!?\n]{0,60}?\b(ready to merge|approve[sd]?|approving|lgtm|looks good( to merge)?)\b/_/gi')"
  cleaned="$(echo "$cleaned" | perl -pe 's/\b(not a |not |no |non-?)(blocker|blockers|blocking|critical|must[ -]?fix)\b/_/gi')"

  # Tier 1: explicit positive signals on the cleaned body. Keep the bare
  # approve alternative anchored so "I approve" matches while "unable to
  # approve" was already neutralized above.
  if echo "$cleaned" | grep -qiE '\b(ready to merge|lgtm|no major issues|no issues|all findings (are )?resolved|looks good( to merge)?|no remaining issues|verdict:[[:space:]]*clean|no blocking findings)\b|(^|[^a-z])(approved|I approve)\b'; then
    return 0
  fi

  # Tier 2: blocker keywords on the cleaned body.
  if echo "$cleaned" | grep -qiE '\b(blocker|blockers|blocking|must fix|critical|fix before merge|do not merge|request(ing|s) changes)\b'; then
    return 1
  fi

  # Ambiguous — conservative default (caller will explicit-ping).
  return 1
}

# Adapter: Copilot reviewer. Approval requires Copilot's latest submitted
# review to have been submitted against the current head SHA
# (review.commit_id == head.sha) and to have 0 inline comments on that commit.
# Inference, not a documented signal.
copilot_is_approved() {
  local head_sha latest_review review_sha inline_count
  head_sha="$(gh api "repos/$owner_repo/pulls/$PR" --jq '.head.sha')"
  latest_review="$(gh api "repos/$owner_repo/pulls/$PR/reviews" --paginate --slurp \
    | jq '[.[][] | select(.user.login == "copilot-pull-request-reviewer[bot]")] | sort_by(.submitted_at) | last')"
  review_sha="$(echo "$latest_review" | jq -r '.commit_id // ""')"
  if [ -z "$review_sha" ] || [ "$review_sha" != "$head_sha" ]; then
    return 1
  fi
  inline_count="$(gh api "repos/$owner_repo/pulls/$PR/comments" --paginate --slurp \
    | jq --arg sha "$head_sha" '[.[][] | select(.user.login == "copilot-pull-request-reviewer[bot]" and .commit_id == $sha)] | length')"
  [ "$inline_count" = "0" ] && return 0
  return 1
}

# Adapter: CodeQL (github-advanced-security[bot]). Per the SKILL.md reviewer
# table, CodeQL's approval signal is "check-run conclusion success", NOT a
# review state. Look up check-runs on the PR's head commit and consider it
# approved iff every CodeQL-related check-run has conclusion=success. If
# CodeQL isn't configured for this repo (no matching check-runs), treat as
# vacuously approved — there's no blocker.
codeql_is_approved() {
  local head_sha statuses
  head_sha="$(gh api "repos/$owner_repo/pulls/$PR" --jq '.head.sha')"

  statuses="$(gh api "repos/$owner_repo/commits/$head_sha/check-runs?per_page=100" --paginate --slurp \
    | jq -c '[.[].check_runs[] | select((.app.slug // "" | test("github-advanced-security|codeql"; "i")) or (.name | test("CodeQL|code-scanning|Analyze \\("; "i"))) | .conclusion]')"

  # No matching check-runs → vacuously approved.
  if [ "$(echo "$statuses" | jq 'length')" = "0" ]; then
    return 0
  fi
  echo "$statuses" | jq -e 'all(. == "success")' >/dev/null && return 0
  return 1
}

# Compute per-reviewer state. We return both an `is_approved` boolean (per the
# adapter for known bots, or the formal review state for everything else) and
# the original `last_review_state` for transparency.
#
# Decommissioned reviewers are dropped outright. The Codex/ChatGPT integration
# is no longer subscribed, so any review it left on an older PR is stale: left
# in place it would match the generic `*[bot]` fallback, never reach the formal
# APPROVED state, and hold `all_bots_approved` false forever.
echo "$repo_data" | jq -c '
  ["chatgpt-codex-connector[bot]", "chatgpt-codex-connector", "codex"] as $decommissioned |
  ([.reviews[]
     | select(.author.login != "'"$pr_author"'")
     | select((.author.login | ascii_downcase) as $l | ($decommissioned | index($l) | not))
     | {login: .author.login, state: .state, submittedAt: .submittedAt}]
    | group_by(.login)
    | map(sort_by(.submittedAt) | last)
    | map({(.login): {state: .state}})
    | add // {}) as $latest |
  $latest | to_entries
' | jq -c '.[]' | while read -r entry; do
  login="$(echo "$entry" | jq -r '.key')"
  state="$(echo "$entry" | jq -r '.value.state')"

  if is_bot_login "$login"; then
    kind="bot"
    case "$login" in
      "claude[bot]"|claude)
        if claude_is_approved; then
          is_approved=true; source="claude-soft-positive-or-no-blockers"
        else
          is_approved=false; source="claude-no-positive-signal-or-blockers"
        fi
        ;;
      "copilot-pull-request-reviewer[bot]"|"copilot-pull-request-reviewer")
        if copilot_is_approved; then
          is_approved=true; source="copilot-zero-inline-comments"
        else
          is_approved=false; source="copilot-has-inline-comments"
        fi
        ;;
      "github-advanced-security[bot]"|"github-advanced-security")
        if codeql_is_approved; then
          is_approved=true; source="codeql-checks-success"
        else
          is_approved=false; source="codeql-checks-not-all-success"
        fi
        ;;
      *)
        # Unknown bot: fall back to formal review state.
        if [ "$state" = "APPROVED" ]; then is_approved=true; else is_approved=false; fi
        source="formal-review-state"
        ;;
    esac
  else
    kind="human"
    if [ "$state" = "APPROVED" ]; then is_approved=true; else is_approved=false; fi
    source="formal-review-state"
  fi

  jq -n --arg login "$login" --arg kind "$kind" --arg state "$state" \
        --argjson is_approved "$is_approved" --arg source "$source" \
        '{($login): {kind: $kind, last_review_state: $state, is_approved: $is_approved, approval_source: $source}}'
done | jq -s --arg pr "$PR" --arg pr_author "$pr_author" '
  (add // {}) as $reviewers |
  ($reviewers | to_entries) as $entries |
  ($entries | map(select(.value.kind == "bot"))) as $bot_entries |
  ($entries | map(select(.value.kind == "human"))) as $human_entries |
  {
    pr_number: ($pr | tonumber),
    pr_author: $pr_author,
    reviewers: $reviewers,
    reviews_seen: (($entries | length) > 0),
    all_bots_approved: (
      (($entries | length) > 0)
      and
      (
        ($bot_entries | length) == 0
        or
        ($bot_entries | all(.value.is_approved == true))
      )
    ),
    any_changes_requested: (
      $entries | any(.value.last_review_state == "CHANGES_REQUESTED")
    ),
    bots_pending_signoff: [$bot_entries[] | select(.value.is_approved == false) | .key],
    humans: [$human_entries[].key],
    bots: [$bot_entries[].key]
  }
'
