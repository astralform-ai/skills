#!/usr/bin/env bash
# list-unresolved-threads.sh <PR#>
#
# Lists all unresolved review threads on a PR, with file:line, author, and body.
# Sorts: bots first (so we address mechanical feedback before human nuance).
#
# Output: JSON array of threads.

set -euo pipefail

PR="${1:?PR number required}"

# Get repo owner/name from current PR (gh handles default repo from cwd).
repo_data="$(gh pr view "$PR" --json url,headRepository,baseRefName 2>/dev/null)"
owner_repo="$(echo "$repo_data" | jq -r '.url | capture("github.com/(?<o>[^/]+)/(?<r>[^/]+)/") | "\(.o) \(.r)"')"
owner="$(echo "$owner_repo" | awk '{print $1}')"
repo="$(echo "$owner_repo" | awk '{print $2}')"

# GraphQL: pull review threads with their first comment (the originating comment).
gh api graphql -f query='
  query($owner: String!, $repo: String!, $pr: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $pr) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            isOutdated
            path
            line
            originalLine
            comments(first: 1) {
              nodes {
                id
                databaseId
                body
                author { login }
                createdAt
              }
            }
          }
        }
      }
    }
  }
' -f owner="$owner" -f repo="$repo" -F pr="$PR" \
  | jq '
    def is_bot_login: (
      endswith("[bot]")
      or . == "claude"
      or . == "copilot-pull-request-reviewer"
      or . == "github-advanced-security"
      or . == "dependabot"
      or . == "renovate"
      or . == "sentry-io"
    );
    [.data.repository.pullRequest.reviewThreads.nodes[]
      | select(.isResolved == false)
      | {
          thread_id: .id,
          comment_id: .comments.nodes[0].databaseId,
          path,
          line: (.line // .originalLine),
          is_outdated: .isOutdated,
          author: (.comments.nodes[0].author.login // "unknown"),
          is_bot: ((.comments.nodes[0].author.login // "") | is_bot_login),
          body: .comments.nodes[0].body,
          created_at: .comments.nodes[0].createdAt
        }
    ]
    | sort_by([(.is_bot | not), .created_at])
  '
