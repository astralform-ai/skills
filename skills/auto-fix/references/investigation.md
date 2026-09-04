# Finding the cause, in a sandbox

Read this once the symptom is pinned down and you need to know *why*. It is the part
between "I can make it happen" and "I know what to change".

## Start from the evidence, not from the code

The temptation is to open the file the symptom seems to name and start reading. That is
how you end up fixing the wrong layer. Work from what you actually observed:

- **Error text is the strongest lead there is.** Grep the repository for it verbatim
  before anything else. It usually lands you within a few lines of the throw site.
- **A stack trace names frames in order.** The interesting one is rarely the top — the top
  is where it surfaced, and the cause is usually a few frames down where a wrong value was
  produced or a guard was missing.
- **"It used to work" is a bisect instruction**, not a feeling. If you have a rough date,
  deepen the shallow clone and look at what changed near it.

```python
import capsule
capsule.proc.exec("cd <REPO_DIR> && grep -rn 'Cannot read properties of undefined' --include='*.ts' .", timeout=90)
capsule.proc.exec("cd <REPO_DIR> && git fetch --depth 100 origin && git log --oneline -20", timeout=120)
```

The clone is `--depth 1`, so `git log` shows one commit and `git blame` is useless until
you deepen it. Deepen deliberately: a full fetch of a large repository can exhaust the
sandbox's disk and will certainly waste minutes of the run's one-hour token.

## Read the code before you believe your theory

Two failure modes cost the most time here, and both feel like progress:

- **Confirming rather than testing.** Once a theory forms, every line seems to support it.
  Deliberately look for the thing that would prove it wrong: if the cause is a null that
  reaches this function, find the caller that can pass one. If you cannot find it, the
  theory is wrong regardless of how well it explains the symptom.
- **Trusting a comment or a name.** A function called `validate` may validate nothing. A
  comment describes what someone intended at some point. The code is the only authority;
  read the body.

## Narrow it with the smallest possible run

Prefer the cheapest reproduction that still fails:

1. A single test, run directly. Seconds, and it becomes the acceptance check.
2. A `python3 -c` or `node -e` that calls the function with the offending input.
3. The whole suite. Slow, and it drowns the signal in noise.

```python
capsule.proc.exec("cd <REPO_DIR> && npx vitest run src/foo/bar.test.ts -t 'the failing case'", timeout=240)
```

Each `proc.exec` is a fresh shell, so `cd <REPO_DIR> &&` goes on every command; there is no
sticky working directory.

## Instrumenting when reading is not enough

Adding a print is legitimate. Leaving it in is not.

```python
capsule.proc.exec("cd <REPO_DIR> && git diff --stat", timeout=60)
```

Run that before committing, every time. Debug output that ships is the most common
avoidable review finding, and in a sandbox it is easy to forget what you added an hour ago
because nothing on screen persists.

## When the cause is not in this repository

Sometimes the honest answer is that the bug is in a dependency, in another service, or in
data. Say so, with the evidence that points there, rather than working around it locally.

A workaround in this repository for a cause in another one is a real decision with real
cost — it hides the problem from whoever owns it, and it usually outlives the bug. That
decision belongs to the user, not to this run.

## What a good report looks like when you stop early

Name three things:

- What you can make happen on demand, and how.
- What you ruled out, and the evidence that ruled it out.
- The one thing you would need in order to continue — an input, an environment, an
  access.

That is worth more than a speculative patch, and it is the difference between someone
picking the work up in ten minutes and starting over.
