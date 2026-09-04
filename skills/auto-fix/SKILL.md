---
name: auto-fix
description: "Take a reported symptom to a pull request, inside this agent's sandbox. Reproduces the symptom in a clone first, turns it into a failing acceptance check, finds the cause, fixes it minimally, proves the check flips, and opens the PR. Use when someone describes something broken and wants it fixed — '/auto-fix the sidebar flickers on reload', 'fix this timeout', 'the export button does nothing, sort it out'. Requires a code-mode agent and a task bound to a project. Do NOT trigger for explaining or investigating without fixing."
display_name: Auto Fix
version: "2.0.0"
author: Astralform
---

# Auto Fix

Take one symptom to a pull request, working entirely inside this agent's sandbox.

## The one idea

**Reproduce it before you fix it, and turn the reproduction into a check.**

`auto-issue` starts from a written issue. This starts from a sentence a person said, which
is weaker evidence: it may describe a symptom of something else, a thing that was already
fixed, or behaviour that is working as designed. So the first work is not finding the fix —
it is making the symptom happen on demand.

A symptom you cannot reproduce is a symptom you cannot prove you fixed. When you truly
cannot, say so and ask for what would let you: the input, the environment, the exact
sequence. Guessing at a plausible patch is how a fix ships that changes nothing.

## Before anything: what you are working in

This runs in a **sandbox**. No worktrees, no existing checkout. The task is bound to one
repository and the run holds a token scoped to exactly it; `git` and `gh` are already
authenticated.

Every shell command goes through the Python kernel:

```python
import capsule
r = capsule.proc.exec("gh repo view --json name", timeout=60)
r["exit_code"]   # 0 on success — ALWAYS check this
```

`capsule.proc.exec` **never raises**. Only `exit_code` tells you a command failed, so
check it every time or a failure will read as success.

- **Always pass `timeout`.** Cells are capped at 300 seconds; anything near 240 goes
  through `capsule.proc.run_background` and a poll.
- **Clone under `./work/`**, relative to the sandbox's working directory. Not `/tmp` (RAM) and not `/workspace` (a network mount).
- **Parse JSON with `gh … --jq '…'` or `python3`.** The E2B code sandbox carries `jq`,
  a Sprites sandbox does not, and `gh --jq` works on both.
- **Scope:** needs `gh`, which the E2B code sandbox has and a Sprites sandbox does not.

## Step 1 — Pin down the symptom

Get these before touching code. If the user gave them, repeat them back; if not, ask:

- What was done, exactly — the input, the URL, the command.
- What happened, in their words, including any error text verbatim.
- What they expected instead.
- Whether it ever worked, and roughly when it changed.

"It's broken" is not a symptom. "Clicking Export on a conversation with no messages shows
a spinner forever, and the console says `Cannot read properties of undefined`" is.

## Step 2 — Clone and reproduce

```python
r = capsule.proc.exec("{baseDir}/scripts/clone.sh owner/repo af/fix-<slug>", timeout=180)
```

Read `REPO_DIR=` from stdout. Then reproduce, in this order of preference:

1. **A test that fails.** Best evidence, and it becomes the acceptance check directly.
2. **A command whose output is wrong.** Record the command and the wrong output.
3. **A code path you can prove is reached with the wrong state.** Weakest; use only when
   the symptom needs a browser or a device the sandbox does not have, and say so plainly.

`references/investigation.md` covers reading the code to find the cause once the symptom
is pinned.

## Step 3 — Turn it into a failing check

Write the check down. Run it. **Watch it fail**, and keep the output.

This is the same rule `auto-issue` follows, for the same reason: a check you never saw
fail is a hope. It also settles the most common disagreement in review — whether a change
does anything — with a fact rather than an argument.

If the check will not fail, one of three things is true, and each has a different answer:

| What you find | What to do |
|---|---|
| It is already fixed on the default branch | Say so, name the commit, stop |
| You are reproducing the wrong thing | Go back to step 1 and get sharper inputs |
| It needs a browser, a device, or scale the sandbox lacks | Say what you cannot reach, and what evidence you can offer instead |

## Step 4 — Find the cause, fix minimally

Fix the cause, not the symptom. A guard that hides a bad value leaves the bad value; the
next symptom from it is harder to trace because the obvious signal is now suppressed.

Only what the symptom asks for. Note anything else you see in the PR body; do not touch it.
Read every file before you edit it.

## Step 5 — Prove it, and run the repo's gate

Re-run the acceptance check: it must pass now and have failed before, in the same run.

```python
r = capsule.proc.exec("{baseDir}/scripts/gate.sh --repo-dir <REPO_DIR>", timeout=280)
```

**Exit code 3 means egress, not a broken repo.** The sandbox reaches `github.com` and
whatever this agent's network policy allows, nothing more. If a dependency install cannot
resolve a host, `gate.sh` prints `EGRESS: allow <host> on this agent` and exits 3. Stop and
name the host. Do not open a PR whose tests never ran.

## Step 6 — Size gate, then open the PR

```python
r = capsule.proc.exec("cd <REPO_DIR> && git status --short && git add -A && git diff --cached --stat origin/HEAD", timeout=60)
```

Read the `git status --short` line first: `gate.sh` ran an install in this tree, so a repo
with no lockfile now has a generated one. Unstage anything the fix did not intend before
committing.

`origin/HEAD` is the default branch's tip **today**, not this branch's fork point — a
`--depth 1` clone has no merge base to use instead. On a resumed task whose default branch
moved meanwhile, that movement is counted too and the number reads high. It errs toward
stopping for a human, which is the right direction to err, but say so rather than splitting
a PR that was never oversized.

Above roughly **500 changed lines**, stop and ask — review stops converging past that.

Push and open the PR (the work is already staged by the size check above):

```python
r = capsule.proc.exec(
    "cd <REPO_DIR> && git commit -m '<message>' && git push -u origin af/fix-<slug>",
    timeout=180,
)
r = capsule.proc.exec(
    "cd <REPO_DIR> && gh pr create --head af/fix-<slug> --title '<title>' --body '<body>'",
    timeout=120,
)
```

No `--base`: `gh pr create` targets the repository's own default branch, which is not
always `main`. `clone.sh` prints `BASE=` if you need the name.

The body carries the symptom as reported, the acceptance check by name, and what it did
before and after. There is no issue number here unless the user named one — if they did,
`Closes #<N>` goes in the body.

## Step 7 — Report

One line: the symptom, the cause, the check that now passes, and the PR link. If you
stopped early, say which stop condition you hit and what you need to continue.

## Stop conditions

- The symptom cannot be reproduced, and you have said what would let you reproduce it.
- The acceptance check will not fail before the fix.
- The cause is in a dependency or another repository rather than this one.
- The diff exceeds the size gate and cannot be split without a design decision.
- `gate.sh` exits 3: a host must be allowed on this agent before the tests can run.
- Anything needs a force-push or history rewrite.
