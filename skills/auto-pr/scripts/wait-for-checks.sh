#!/usr/bin/env bash
# wait-for-checks.sh <PR#> [--required-only]
#
# Returns the PR's check-run state as JSON. Does NOT block — call this from
# inside a ScheduleWakeup loop, not in a tight poll.
#
# Output:
# {
#   "pr_number": 123,
#   "all_required_passed": false,
#   "any_in_progress": true,
#   "any_failed": false,
#   "checks": [
#     { "name": "build", "status": "completed", "conclusion": "success", "required": true },
#     { "name": "CodeQL", "status": "in_progress", "conclusion": null, "required": true },
#     ...
#   ]
# }
#
# `required: true` is set if the check name appears in branch protection's required list.
# If branch protection cannot be read (no admin), all checks default to required=null
# and `all_required_passed` falls back to "all checks passed".

set -euo pipefail

PR="${1:?PR number required}"

pr_data="$(gh pr view "$PR" --json statusCheckRollup,baseRefName,baseRepository,url 2>/dev/null)"

# Try to fetch required checks from branch protection.
required_checks_json='[]'
if owner_repo="$(echo "$pr_data" | jq -r '.url | capture("github.com/(?<o>[^/]+)/(?<r>[^/]+)/") | "\(.o)/\(.r)"')"; then
  base="$(echo "$pr_data" | jq -r .baseRefName)"
  if protection="$(gh api "repos/$owner_repo/branches/$base/protection" 2>/dev/null)"; then
    required_checks_json="$(echo "$protection" | jq '[.required_status_checks.contexts[]?] // []')"
  fi
fi

echo "$pr_data" | jq --argjson required "$required_checks_json" '
  ($required | length > 0) as $have_required |
  [.statusCheckRollup[] |
    {
      name: (.name // .context),
      status: (.status // "completed"),
      conclusion: (.conclusion // .state // null),
      required: ($have_required and (any($required[]; . == (.name // .context))))
    }
  ] as $checks |
  {
    pr_number: ('"$PR"' | tonumber),
    have_required_list: $have_required,
    all_required_passed: (
      if $have_required then
        ($checks | map(select(.required)) | all(.conclusion == "success" or .conclusion == "SUCCESS" or .conclusion == "neutral" or .conclusion == "skipped"))
      else
        ($checks | all(.conclusion == "success" or .conclusion == "SUCCESS" or .conclusion == "neutral" or .conclusion == "skipped"))
      end
    ),
    any_in_progress: ($checks | any(.status == "in_progress" or .status == "queued" or .status == "pending" or .status == "IN_PROGRESS" or .status == "QUEUED" or .status == "PENDING")),
    any_failed: ($checks | any(.conclusion == "failure" or .conclusion == "FAILURE" or .conclusion == "timed_out" or .conclusion == "TIMED_OUT" or .conclusion == "cancelled" or .conclusion == "CANCELLED")),
    checks: $checks
  }
'
