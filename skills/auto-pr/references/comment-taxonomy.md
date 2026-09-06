# GitHub's four comment shapes, and which one you can resolve

Read this when a reply lands in the wrong place, when a thread will not resolve,
or when writing a query of your own against a pull request's conversation.

GitHub has four overlapping concepts that look nearly identical in JSON. Only
one of them is resolvable, and only one of them is what a review finding lives
in.

| Concept | API | What it is |
|---|---|---|
| **Issue comment** | `/issues/{n}/comments` | A top-level comment on the pull request, with no line anchor. Review bots usually post their summary here. Not resolvable. |
| **Review** | `/pulls/{n}/reviews` | A grouping object with a state (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`). Often has an empty body and exists only to wrap inline comments. |
| **Inline review comment** | `/pulls/{n}/comments` | A comment anchored to a file and line, inside a thread. **These are the findings.** |
| **Review thread** | GraphQL `reviewThreads` | The resolvable container around those inline comments. Node id like `PRRT_…`. |

## Two identifiers, two APIs, not interchangeable

Each thread carries both, and the gate reports both:

- **`comment_id`** — an integer `databaseId`. REST. This is what you reply to.
- **`thread_id`** — a `PRRT_…` node id. GraphQL. This is what you resolve, and
  it is the thread's stable identity, so key any bookkeeping of your own on it.

Passing one where the other belongs produces a 404 that reads like a permission
problem.

`comment_id` points at the **latest reviewer comment** in the thread, not the
opening one, so a reply lands under the remark being answered rather than at the
top of a long conversation.

## Reply and resolve are two operations

The GitHub UI conflates them: writing a reply in the web interface and clicking
"Resolve conversation" feel like one action. Through the API they are two calls,
and doing only one is a visible failure mode.

- **Reply alone** leaves the thread open forever. A reader sees an unanswered
  conversation on a merged pull request.
- **Resolve alone** leaves no record of the decision. The gate re-derives the
  thread as unclassified next round, and a reviewer reading the pull request
  sees a conversation closed with no explanation.

Reply first, with a marker, then resolve. In that order: resolving before
replying leaves the reviewer's comment newer than yours, which the gate reads as
an escalation.

## Replying through GraphQL instead

REST is not the only path. `addPullRequestReviewThreadReply` takes the
`pullRequestReviewThreadId`, so if you already hold the thread id and not the
comment id, use it. Resolving has no REST equivalent — `resolveReviewThread` is
GraphQL only, which is the whole reason two scripts exist.
