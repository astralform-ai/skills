# The code-change path, in a sandbox

Read this when triage says the issue needs a repository edit. It is the long form of
steps 5 to 8; the rules here are the ones that cost something when skipped.

## There is no worktree

On a laptop the loop branches a worktree off the main checkout so the user's tree stays
untouched. There is no checkout here and nothing to protect: the sandbox is created for
this run and destroyed with it. So the shape is **clone, branch, push** — and every clone
is disposable, which means a mistake is recoverable by cloning again rather than by
unwinding.

Two consequences worth holding onto:

- **Nothing survives the run.** The clone, the installed dependencies, the branch you
  checked out locally — all gone when the job ends. What survives is what you pushed.
  Push before you finish, or the work is lost.
- **The token is scoped to one repository and lives for an hour.** Long installs and long
  test suites eat into that. Push early rather than at the very end.

## Clone

```python
import capsule
r = capsule.proc.exec("./skills/auto-issue/scripts/clone.sh owner/repo af/issue-42", timeout=180)
assert r["exit_code"] == 0, r["stderr"]
```

Read `REPO_DIR=` out of stdout. Every later command is `cd $REPO_DIR && …`, because each
`proc.exec` starts a fresh shell in the sandbox home — there is no persistent cwd.

The clone is shallow (`--depth 1 --single-branch`). That is enough to edit, commit and
push. It is not enough to read history: `git log` shows one commit, and `git blame` is
useless. If the issue turns on how something came to be, fetch what you need explicitly:

```python
capsule.proc.exec("cd $REPO_DIR && git fetch --depth 50 origin", timeout=120)
```

Deepen deliberately, not by default. A full fetch on a large repository can exhaust the
disk and will certainly waste minutes of the token's hour.

## Make the fix minimal

The issue names one problem. Fix that one.

Drive-by improvements are the single most reliable way to make a PR unreviewable: the
diff grows, the reviewer re-reads all of it on every push, and the finding count grows
with it. If you spot something else, write it in the PR body as an observation. Do not
touch it.

Read every file before you edit it. An issue's `file:line` reference can be months old,
and the sandbox's shallow clone gives you no history to notice that with.

## Prove the fix

The acceptance check from step 4 must **fail before and pass after**, in the same run.
Demonstrating that is the whole point of writing it first, so do not skip re-running the
failing case just because the fix looks obviously right.

If the check involves a test file you added, prove the test is not vacuous: stash the
source change, run the test, watch it fail, restore.

```python
capsule.proc.exec("cd $REPO_DIR && git stash push -- <source-file>", timeout=60)
# run just the new test — it must FAIL
capsule.proc.exec("cd $REPO_DIR && git stash pop", timeout=60)
# run it again — it must PASS
```

A test that passes with and without the fix is worse than no test: it makes a future
change look safe when it is not.

## Long commands

A cell is capped at 300 seconds and `gate.sh` defaults to a 240 second budget. A real test
suite can exceed both. When it does:

```python
h = capsule.proc.run_background("cd $REPO_DIR && npm test > /tmp/test.log 2>&1")
# poll, with a timeout on each poll
capsule.proc.exec("tail -5 /tmp/test.log", timeout=30)
```

Poll until it finishes rather than raising the cell timeout, and read the log at the end.

## Egress

The sandbox reaches `github.com` and `api.github.com` because this run holds a repository
token, plus whatever the agent's own network policy allows. Nothing else.

That is enough to clone, push and open a PR. It is often **not** enough to install
dependencies: a registry, a CDN for prebuilt binaries, or a proxy may all be unreachable.
`gate.sh` detects that case and exits 3 with the host named.

When it does, stop. Report which host must be allowed on this agent. Do not open a PR
whose tests never ran and do not describe it as verified — an unverified fix presented as
a verified one is worse than no PR.

## The PR

- `Closes #<N>` goes in the **body**. That is what closes the issue on merge; in a commit
  message it does nothing.
- The body names the acceptance check and what it did before and after. That is the one
  thing that makes review fast, because it turns "would this break?" into a fact.
- Match the repository's commit voice. `git log --oneline -20` shows the prefix style.
- Never force-push, never rewrite history, never commit to the default branch.
- Never put a token in a URL. `clone.sh` configures gh's credential helper precisely so
  you never have to.
