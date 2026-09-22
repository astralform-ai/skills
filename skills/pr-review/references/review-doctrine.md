# Review doctrine

The judgement layer for `pr-review`: what to flag, how to read a hunk, how to write a finding,
and how a re-review behaves. The mechanics live in `SKILL.md`; this file is why they look that
way. Every rule here is load-bearing — most exist because a pull request paid for the failure
they prevent.

## What to flag

- **Be thorough on bugs and security.** Do not skip a genuine problem because the trigger
  scenario is narrow. Narrow-but-real beats loud-but-vague.
- **Be certain before flagging low-severity concerns.** If you cannot confidently explain why
  something is a problem with a concrete scenario, do not flag it.
- **Each finding is discrete and actionable.** Not a vague concern about the codebase in general.
  A finding that cannot be fixed by a diff is not a finding.
- **No speculation without a path.** Do not claim a change might break other code unless you can
  name the specific affected code path from the diff context.
- **Do not flag intentional design choices or stylistic preferences** unless they introduce a
  clear defect. The author chose it; "I would have written it differently" is not a review.
- **High impact + low confidence** — data loss, security: report it, with an explicit note on
  what remains uncertain. Otherwise prefer not reporting to guessing.
- **An empty findings list is a valid answer.** CLEAN is the expected outcome of a good PR and of
  most re-reviews. It is a complete review, not a failure to find anything.

## Reading the diff

The hunk is the whole world, and it is not the whole world:

- **Only lines the PR adds are in scope for findings.** Removed lines are read for context —
  "you deleted the only caller of X" is a finding about the surviving code, not about the
  deleted line.
- **You see changed segments, not the codebase.** Do not question declarations, imports, or
  helpers that may be defined elsewhere. If a symbol's absence is load-bearing for your finding,
  go read the file before claiming it is missing.
- **Code ending at an opening brace or scope-introducing statement is not incomplete.**
  Acknowledge the visible scope boundary and analyse the code shown.
- **Report on code the PR touches.** The one re-review exception is in `SKILL.md`: a delta that
  breaks something outside itself, with both locations cited.

## The severity boundary

`[BLOCKING]` — the change is wrong, and you can name a concrete input that produces a wrong
output. Broken behaviour, a guard that does not hold, data loss, a leak, a race, an unhandled
error path, a broken contract, a security hole, or a test that passes both with and without the
change.

`[NIT]` — everything else. Stale or imprecise comments, docstrings and markdown; naming;
wording; readability; "consider extracting"; "you could also handle X"; anything whose fix grows
the diff.

Two rules on that boundary, because they are where this goes wrong:

1. **Documentation coherence is ALWAYS `[NIT]`.** A docstring, comment, or markdown file that
   contradicts the code is a real defect and is never blocking. Provably wrong is what makes it
   worth reporting — not what makes it worth blocking.
2. **If you cannot name the input that produces the wrong output, it is `[NIT]`.** "This could
   confuse a reader" and "a future maintainer might" are nits. Strength of wording is not
   severity.

When unsure, label `[NIT]`. A missed nit costs a line of prose; a mislabelled blocker costs a
full review round — a push, a CI cycle, and a review — of somebody's life.

### Examples

| Finding | Label | Why |
|---|---|---|
| `user.id` dereferenced behind a guard the caller can bypass with `None` | `[BLOCKING]` | Nameable input, wrong output (crash) |
| `except Exception: pass` swallowing errors in a retry loop | `[BLOCKING]` | Silent failure path; input is any transient error |
| A new test whose assertion passes with and without the fix | `[BLOCKING]` | The test proves nothing; the PR's safety claim rests on it |
| Live credentials in a new fixture file | `[BLOCKING]` | Leak; the input is the commit itself |
| Docstring says "returns sorted ids" over code that no longer sorts | `[NIT]` | Documentation coherence — always a nit, however wrong |
| "Consider extracting this 40-line function" | `[NIT]` | The fix grows the diff |
| "This might break other callers" without naming one | Do not report | Speculation without a path |

## Writing the finding

- **The anchor carries the location.** The body never repeats line numbers — they go stale on
  the next push, and the inline-comment anchor does not.
- **Backticks** for every variable, symbol, and path, never single quotes.
- **Name the scenario.** Why it matters and the concrete input that triggers it, in one or two
  sentences. If the issue only manifests under specific inputs or environments, say so upfront —
  communicated severity must be accurate; do not overstate impact.
- **Concise.** The reader grasps the point immediately, without close reading. One finding per
  thread; never bundle two defects into one comment.
- **Matter-of-fact tone.** No accusations, no praise, no filler. "Great job" and "Thanks for"
  are noise.
- **The header is two words.** "Possible bug", "Race", "Leak". The body argues; the header files.

## Re-reviews

- **The delta is the new work.** Read wider for context; report on the delta.
- **An open thread means the author has not replied yet.** Do not re-raise, restate, or sharpen
  a finding you already made. Your silence on open threads is what lets a merge loop converge.
- Findings per push should decay across rounds. Flat or rising means you are re-reading the
  whole diff — go back to the delta protocol.
- The one exception stands: a delta that breaks something outside itself, with both locations
  cited.

## The verdict

- `VERDICT: CLEAN — no blocking findings` or `VERDICT: BLOCKING — <n> blocking finding(s)`. The
  last line of the summary, on its own line, spelled exactly — a driver reads it mechanically.
- You are one half of an automated loop with a finite round budget. You label; the driver
  decides. A `[BLOCKING]` finding costs a full round; a `[NIT]` is recorded and merged past.
- Do not inflate severity to force attention — nits are read.
- Do not withhold CLEAN because nits remain. Withholding it does not make the PR better; it
  makes the loop spin, and a loop that cannot converge gets abandoned with the PR still open.
