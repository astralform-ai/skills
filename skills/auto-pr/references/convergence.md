# Why review loops run away, and what actually stops them

Read this before relaxing any rule in `SKILL.md`, when a loop is running long, or
when changing a repository's review trigger. The rules live in the skill; the
evidence lives here, because you need the rule every round and the evidence only
when you doubt it.

## The model: findings per push is a reproduction number

A reviewer handed a diff always returns *something*, so "are there findings?" was
never a stopping rule. What decides whether a loop terminates is the rate:

> **f = new findings the reviewer produces per push.**
>
> Each round you fix some findings and push once, which buys a full re-review
> that produces f more. Below about f = 1 the loop drains and converges. Above
> it, each round creates more work than it closes and the loop is supercritical:
> it terminates only on a budget, an abandonment, or a person noticing.

This is why the fix is a **budget and a severity gate**, not better advice about
batching. Advice cannot lower f. Only two things can: acting on fewer findings
(the severity gate) and pushing fewer times (batching).

The rate is not a constant. It moves with the reviewer's model, its prompt, and
the diff size, and it has tripled overnight from a reviewer-side change with no
warning. A loop whose termination depends on f staying low is a loop that will
one day not terminate.

## The three observed failure shapes

### Prose churn feeds itself

The most expensive one, and the least obvious. On a long-running pull request,
the first commit was the actual fix and the next nine were all prose. Each was
driven by a finding the previous prose fix had created:

- a docstring left as the last surviving reference to a path the change deleted
- a sentence ten lines below an edit that no longer followed from it
- a comment made provably wrong by a warning added two commits earlier

Every prose fix invalidated a different reference, which the next full re-read
found. The agent was its own fuel. **The prose freeze forbids nine of those ten
commits**, and structurally classifying prose-file threads as nits is what makes
the freeze cheap to obey rather than a judgement call every round.

### The diff grows under review

A single guard became 803 changed lines, a major version bump, and six unrelated
fixes — each addition a reasonable response to a reasonable finding. Finding
volume scales with diff size, and the reviewer re-reads the whole thing every
push, so a growing diff raises f exactly when you need it to fall.

### The loop waits for a signal that never comes

Two versions of this. Waiting for the reviewer to say it is satisfied: review
bots do not set GitHub's approved state, and a bot that sounds happy is not a
state you can branch on. And waiting for a review run whose workflow name the
gate guessed wrong: zero matching runs reads as "never reviewed", so the verdict
sits on wait-for-review forever while the pull request is in fact fully
reviewed. The gate falls back to counting every pull-request run and warns, on
the principle that a conservative superset beats a confident zero.

## Why the exit condition is what it is

**Zero unresolved BLOCKING findings, on code a reviewer has seen.**

Both halves are load-bearing. Without the severity gate, the exit depends on the
reviewer falling silent, which above f = 1 never happens. Without "on code a
reviewer has seen", the loop can merge a final push nobody looked at — which is
exactly the hole an unreviewable pull request opens, since a review run that
fails to authenticate is indistinguishable from one that found nothing.

Nits stay open at merge, deliberately, and the merge body says how many. That is
the loop ending on purpose rather than ending because it ran out.

## Why a classification has to be written down

Severity was originally re-derived from comment prose on every run. A thread
judged a nit came back unclassified the next round, and the round after, so the
verdict stuck on classify forever while the agent re-answered the same threads.
Resolving was the only durable signal, which forced the loop to resolve nits
immediately just to record a decision — and resolution is the wrong carrier,
because a reviewer can reopen a thread and the decision would vanish with it.

The marker in the reply body is the record. It survives resolution, it survives
a reviewer escalating on top of it (which correctly resets the thread), and it
is invisible in the rendered comment.

## Why an escalation beats every other rule

Reading severity from a thread's opening comment alone once let a reviewer
escalate a nit into a data-loss finding in a follow-up comment, invisibly, on a
thread already marked and resolved. The gate would have merged over it. On one
long pull request, 30 of 34 threads carried a follow-up, so this is the common
case and not an edge one.

Hence: any reviewer comment newer than your last reply resets the thread to
unclassified, whatever it was marked and whether or not it is resolved. The cost
is re-answering a thread occasionally. The alternative cost is merging a defect
a reviewer explicitly named.
