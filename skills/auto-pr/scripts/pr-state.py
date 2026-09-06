#!/usr/bin/env python3
"""pr-state.py <PR#> — the whole decision state for the auto-pr loop, as one JSON object.

The loop branches on ``.verdict`` and nothing else. Every other field exists so a
person reading the transcript can see why that verdict was reached.

This script exists because the obvious exit condition — "the reviewer has nothing
left to say" — is unreachable whenever the reviewer produces more than about one
finding per push, and a capable reviewer handed a diff always produces more. The
exit therefore has to be a state the DRIVER owns: zero unresolved BLOCKING
findings, on code a reviewer has seen. See references/convergence.md.

Python rather than shell + jq: ``jq`` is NOT installed in the agent's sandbox
(only ``gh``'s built-in ``--jq``, which filters an API response and cannot
transform local JSON). ``python3`` is. One program also beats forty subprocesses.

Exit codes: 0 with JSON on stdout is the only case that carries a verdict. 75 means the gate
could not READ the pull request or its review — transient, so schedule the next iteration and
re-read. 64 is a bad argument and 1 is unusable data; neither is retryable, so surface those.

Environment:
  GH_REPO                  owner/repo — set this; the sandbox clone may not exist yet
  AUTO_PR_ROUND_BUDGET     default 3
  AUTO_PR_REVIEW_WORKFLOW  default "PR Review"

Output schema:
  {
    "pr": int, "head_sha": str,
    "round": int,               # completed reviews on distinct shas
    "round_budget": int,
    "warnings": [str, ...],
    "review_check": {"workflow": str, "conclusion": str|None,
                     "on_head": bool, "flake_suspected": bool},
    "threads": {"blocking": [...], "nit": [...], "unclassified": [...]},
    "counts": {"blocking": n, "nit": n, "unclassified": n,
               "settled": n, "escalated": n, "total_threads": n},
    "checks": {"all_green": bool, "failing": [str, ...], "pending": n,
               "oldest_pending_minutes": float|None,
               "gated_on_required_list": bool},
    "mergeable": str, "merge_state": str,
    "human_changes_requested": bool, "unreviewable": bool,
    "verdict": "MERGE|FIX_BLOCKING|CLASSIFY|WAIT_REVIEW|WAIT_CHECKS|ESCALATE"
  }

Each thread is {thread_id, comment_id, path, line, author, body, severity,
resolved, outdated, escalated, reopened, answered, marker, comments}.
``comment_id`` is the LATEST REVIEWER comment — the right reply target — not the
thread's opening one. ``thread_id`` is the stable identity.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

# Our own classification marker. The reply templates in SKILL.md write it; this
# reads it back, which is what makes a classification durable across rounds.
MARKER_RE = re.compile(r"<!-- *auto-pr:(fixed|nit|wrong) *-->")
SEVERITY_MARKER = {
    "blocking": re.compile(r"^\s*\[BLOCKING\]", re.IGNORECASE),
    "nit": re.compile(r"^\s*\[NIT\]", re.IGNORECASE),
}
PROSE_SUFFIXES = (".md", ".mdx", ".txt", ".rst")
# Any workflow whose filename looks like a review. The workflow NAME is configurable
# (AUTO_PR_REVIEW_WORKFLOW), so pinning this to two filenames left a repo that renamed its
# review workflow with a working round count and a silently dead unreviewable guard — the one
# guard standing between the loop and merging unreviewed code. `review` must follow a
# separator or start the name: `preview.yml` is a deploy preview, not a reviewer, and
# escalating on it hands a person a non-problem on the first iteration. `claude.yml` stays
# named because that is the filename claude-code-action installs and many repos review from it.
REVIEW_WORKFLOW_PATH = re.compile(
    r"\.github/workflows/(?:(?:[^/]*[-_.])?review[^/]*|claude)\.ya?ml$", re.IGNORECASE
)

PR_FIELDS = (
    "url,number,state,headRefName,baseRefName,headRefOid,mergeable,"
    "mergeStateStatus,statusCheckRollup,reviews,author,files"
)

# Exit codes. The loop has to tell "come back and re-read" from "stop", and only the status is
# available when the refusal prints no JSON — so the transient case gets its own.
EXIT_USAGE = 64  # sysexits EX_USAGE — a bad argument. Permanent; fix the call.
EXIT_TEMPFAIL = 75  # sysexits EX_TEMPFAIL — could not READ. Transient; schedule and re-read.
EXIT_BUG = 1  # read fine, the data is unusable. Not retryable; surface it.

FAILED_CONCLUSIONS = {"FAILURE", "TIMED_OUT", "CANCELLED", "ERROR", "STARTUP_FAILURE"}
PENDING_STATUSES = {"IN_PROGRESS", "QUEUED", "PENDING", "WAITING"}

# Substring-based on purpose. The Codex connector logs in as
# `chatgpt-codex-connector`, which an anchored `^codex$` does not match, and the
# old gate therefore promoted a bot to a human and escalated forever. Same trap
# for `copilot-pull-request-reviewer`, which lacks the `[bot]` suffix on several
# surfaces.
BOT_SUBSTRINGS = (
    "codex",
    "copilot",
    "dependabot",
    "renovate",
    "github-advanced-security",
    "sentry-io",
    "github-actions",
    "greptile",
    "coderabbit",
)


def gh_run(*args: str) -> tuple[int, str]:
    """Run `gh` and return (exit status, stdout). The status is the point: several callers
    below must tell "the API said nothing" from "the API could not be reached", and an empty
    string cannot carry that difference."""
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=120  # noqa: S603,S607
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
    return proc.returncode, proc.stdout


def gh(*args: str, check: bool = True) -> str:
    """Run `gh` and return stdout. Returns "" on failure when check is False.

    Use `check=False` ONLY where a failure degrades safely — toward waiting, or toward a wider
    gating set. Where a failure would degrade toward MERGE, use `gh_run` and read the status.
    """
    code, out = gh_run(*args)
    if code != 0:
        if check:
            # TEMPFAIL, not EXIT_BUG. `raise SystemExit("...")` with a STRING exits 1, and once
            # the exits were split, 1 means "stop, this is a bug" — so a 502 or a rate limit on
            # `gh pr view` ended the goal instead of costing one re-read. A non-zero `gh` is
            # always a READ failure and never unusable data. The permanently-unreadable case (a
            # wrong GH_REPO, a deleted PR) is bounded by max_no_progress_continuations.
            sys.stderr.write(f"gh {' '.join(args)} failed (exit {code})\n")
            raise SystemExit(EXIT_TEMPFAIL)
        return ""
    return out


def gh_json(*args: str, default=None, check: bool = True):
    out = gh(*args, check=check).strip()
    if not out:
        return default
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return default


def is_bot(login: str) -> bool:
    low = (login or "").lower()
    if low.endswith("[bot]") or low in {"claude", "codex"}:
        return True
    return any(s in low for s in BOT_SUBSTRINGS)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Severity classification, in precedence order                                 #
# --------------------------------------------------------------------------- #
#
# 1. ESCALATION WINS OVER EVERYTHING. A reviewer comment newer than our last
#    reply resets the thread to `unclassified` — even one we marked, even one
#    that is resolved. It is the only way a reviewer can correct a call we got
#    wrong, and reading severity off the OPENING comment alone once let a
#    reviewer escalate to "this is data loss" invisibly, over which the gate
#    would have merged.
#
# 2. SETTLED, dropped from the gate: the thread is resolved and nobody has
#    spoken since, or our last reply carries an `<!-- auto-pr:... -->` marker.
#    The marker is what makes a decision DURABLE — without it severity is
#    re-derived from prose every round, a thread we called a NIT comes back
#    unclassified forever, and the verdict sticks on CLASSIFY.
#
# 3. An explicit [BLOCKING] / [NIT] at the start of ANY reviewer comment.
#
# 4. STRUCTURAL: a thread anchored to a prose file is a NIT by construction.
#    Documentation coherence never blocks a merge, and prose churn is the single
#    biggest source of non-converging loops: each fix invalidates a different
#    reference, which the next review finds.
#
# 5. Otherwise unclassified — the agent decides, using SKILL.md's table.
#
# There is deliberately NO keyword heuristic. An honest "unclassified" the agent
# must answer beats a confident wrong label.
def resolve_self_login(threads: list[dict], author: str) -> tuple[str, str | None]:
    """Which login are WE? Returns ``(login, warning)``.

    This is not the PR author. `/auto-pr 123` is meant to be run against someone else's pull
    request, and the reply lands as whatever account the run's token belongs to. Reading "our
    last reply" off the PR author would then find nothing: escalation detection collapses
    (a reviewer coming back on a resolved thread stays `settled`, and the gate merges over it)
    and every marker is invisible, so classifications never persist.

    Four sources, in order:

    1. A comment carrying our own `auto-pr` marker. This one CANNOT be wrong — the marker is
       written by this loop, so whoever posted it is us, whatever the token thinks. It outranks
       the override for that reason; an override that silently contradicts observed evidence is
       worse than no override.
    2. ``AUTO_PR_SELF_LOGIN``, ahead of the remaining detection because an override exists to
       correct a detection that is WRONG, not merely absent — behind all of it, it could never
       fix the case an operator would reach for it.
    3. `gh api user`. Right for a personal token; a GitHub App installation token gets a 403
       here, which is why it is not the only source.
    4. The PR author, which is correct only when the agent opened the pull request.
    """
    override = os.environ.get("AUTO_PR_SELF_LOGIN", "").strip()
    for thread in threads:
        for comment in reversed((thread.get("comments") or {}).get("nodes") or []):
            if MARKER_RE.search(comment.get("body") or ""):
                observed = (comment.get("author") or {}).get("login") or author
                if override and override != observed:
                    return observed, (
                        f"AUTO_PR_SELF_LOGIN is {override!r}, but a reply carrying this loop's "
                        f"own marker was posted by {observed!r}. Trusting the marker, which is "
                        "evidence rather than configuration. Unset the override if it is stale."
                    )
                return observed, None
    if override:
        return override, None
    code, out = gh_run("api", "user", "--jq", ".login")
    if code == 0 and out.strip():
        return out.strip(), None
    return author, (
        "Could not determine which account this run posts as (no marked reply yet, and "
        "`gh api user` is not available to this token — an App installation token gets 403). "
        f"Assuming the PR author, {author!r}. If the run posts as someone else, escalation "
        "detection is blind until the first marked reply; set AUTO_PR_SELF_LOGIN to fix it now."
    )


def classify_thread(thread: dict, author: str, me: str) -> dict | None:
    comments = (thread.get("comments") or {}).get("nodes") or []
    if not comments:
        return None
    originator = (comments[0].get("author") or {}).get("login") or ""
    # A thread the PR author opened is not an outstanding request against the author. Judged on
    # the ORIGINATOR: our own replies are the latest comment on nearly every thread we have
    # answered.
    if originator == author:
        return None

    ours = [c for c in comments if ((c.get("author") or {}).get("login") or "") == me]
    theirs = [c for c in comments if ((c.get("author") or {}).get("login") or "") != me]
    # There is deliberately NO drop for a thread whose only participant is us. Two attempts at
    # one lived here and both merged over a real finding: "we opened it" swallowed a thread the
    # operator opened as a reviewer, and "we opened it and nobody answered" swallowed the very
    # shape it was meant to save — an operator leaves an inline [BLOCKING] and types /auto-pr,
    # so the thread has exactly one comment and nobody has answered YET. With a shared login
    # between the reviewing bot and the replying account that is EVERY thread.
    #
    # The distinguishing fact was never "has someone else spoken" but "have WE answered", and
    # the severity precedence below already encodes it: a resolved thread is settled, our own
    # marker is settled, and anything else classifies — converging in one round, because our
    # marked reply is what settles it. A self-only thread cannot sit unclassified forever
    # without a special case, so there is no special case. The one place that chain needs help
    # is a SHARED login, where "a reviewer spoke after us" has no `theirs` to read; the
    # escalation test below handles it off the marker instead.
    last_ours = ours[-1] if ours else None
    last_theirs = theirs[-1] if theirs else None

    # Escalation normally means "a reviewer spoke after us". With a shared login between the
    # reviewing bot and the replying account there is no `theirs` to compare against, and the
    # precedence chain would settle a resolved thread the reviewer had come back to. The marker
    # still separates the two: anything after our last MARKED comment is a new request. Scoped
    # to the no-third-party shape so our own unmarked follow-up cannot escalate a normal thread.
    escalated = False
    if last_ours is not None and last_theirs is not None:
        escalated = (last_theirs.get("createdAt") or "") > (last_ours.get("createdAt") or "")
    elif not theirs and ours:
        marked_at = [
            c.get("createdAt") or "" for c in ours if MARKER_RE.search(c.get("body") or "")
        ]
        escalated = bool(marked_at) and (ours[-1].get("createdAt") or "") > max(marked_at)

    marker = None
    if last_ours is not None:
        found = MARKER_RE.search(last_ours.get("body") or "")
        marker = found.group(1) if found else None

    # With no third party in the thread, the request lives in OUR OWN comments — a review the
    # operator left before this run started driving the PR. Reading severity off an empty list
    # returns `unclassified` for an explicit [BLOCKING], so FIX_BLOCKING never fires.
    reviewer_bodies = [c.get("body") or "" for c in (theirs or comments)]
    has_blocking = any(SEVERITY_MARKER["blocking"].search(b) for b in reviewer_bodies)
    has_nit = any(SEVERITY_MARKER["nit"].search(b) for b in reviewer_bodies)

    latest = last_theirs or comments[0]
    resolved = bool(thread.get("isResolved"))
    path = thread.get("path") or ""

    if escalated:
        severity = "unclassified"
    elif resolved or marker is not None:
        severity = "settled"
    elif has_blocking:
        severity = "blocking"
    elif has_nit or path.lower().endswith(PROSE_SUFFIXES):
        severity = "nit"
    else:
        severity = "unclassified"

    return {
        "thread_id": thread.get("id"),
        "comment_id": latest.get("databaseId"),
        "path": path,
        "line": latest.get("line") or latest.get("originalLine"),
        "author": (latest.get("author") or {}).get("login") or "unknown",
        "outdated": bool(thread.get("isOutdated")),
        "resolved": resolved,
        "escalated": escalated,
        "reopened": resolved and escalated,
        "answered": last_ours is not None,
        "marker": marker,
        "comments": len(comments),
        "body": latest.get("body") or "",
        "severity": severity,
    }


# --------------------------------------------------------------------------- #
# The verdict chain — the loop's single branch point                           #
# --------------------------------------------------------------------------- #
#
# Reaching the mergeStateStatus branches means everything the gate OWNS has
# passed. What is left is GitHub's own view, and it must be mapped EXPLICITLY.
# A bare "else ESCALATE" reads as a safe default and is not one: ESCALATE stops
# the loop and hands a person a problem, so spending it on a state that is
# merely transient trains them to ignore it. Three states were escalated wrongly
# before this was written out:
#
#   UNKNOWN    GitHub computes mergeability lazily, so the first query on a cold
#              PR returns UNKNOWN and the gate was non-deterministic — the same
#              PR seconds apart returned ESCALATE, then MERGE.
#   UNSTABLE   Mergeable, with a NON-required check red. The gate computes
#              all_green over the branch-protection required list precisely so
#              an advisory check cannot block forever; escalating here threw
#              that away.
#   HAS_HOOKS  Mergeable, passing, pre-receive hooks configured. A server
#              detail, not a finding.
#
# Being permissive here is safe in a way being restrictive is not: `gh pr merge`
# is the real enforcement and refuses if GitHub disagrees, so a wrong MERGE
# costs one loud failed command while a wrong ESCALATE costs a person's
# attention every time it fires.
def decide_verdict(s: dict) -> dict:
    if s["mergeable"] == "CONFLICTING" or s["merge_state"] == "DIRTY":
        return {
            "verdict": "ESCALATE",
            "note": "Merge conflict with the base branch. Rebasing is destructive — "
            "hand to the user.",
        }
    if s["human_cr"]:
        return {"verdict": "ESCALATE", "note": None}
    if s["unreviewable"]:
        return {"verdict": "ESCALATE", "note": None}
    if s["round"] >= s["budget"] and s["blocking"] > 0:
        return {"verdict": "ESCALATE", "note": None}
    # A check that is RED at budget is not going to go green by waiting: an infra credential the
    # sandbox cannot supply, a suite that fails deterministically. Without this the loop spins
    # every remaining continuation on WAIT_CHECKS and nobody hears about it. A check merely
    # RUNNING at budget is a different thing and still just waits.
    if s["round"] >= s["budget"] and s["failing"] > 0:
        return {
            "verdict": "ESCALATE",
            "note": "A check is still failing after the round budget — it is not going to pass "
            "by waiting. See checks.failing.",
        }
    if s["unclassified"] > 0:
        return {"verdict": "CLASSIFY", "note": None}
    if s["blocking"] > 0:
        return {"verdict": "FIX_BLOCKING", "note": None}
    if not s["all_green"]:
        return {"verdict": "WAIT_CHECKS", "note": None}
    if not s["review_on_head"]:
        return {"verdict": "WAIT_REVIEW", "note": None}

    state = s["merge_state"]
    if state in ("CLEAN", "HAS_HOOKS"):
        return {"verdict": "MERGE", "note": None}
    if state == "UNSTABLE":
        return {
            "verdict": "MERGE",
            "note": "GitHub reports UNSTABLE: a NON-required check is red or pending. "
            "The required set is green, which is what gates here. `gh pr merge` will "
            "refuse if GitHub disagrees.",
        }
    if state == "UNKNOWN":
        return {
            "verdict": "WAIT_CHECKS",
            "note": "GitHub reports mergeability UNKNOWN. It computes this lazily, and "
            "this script re-queries while the PR is OPEN, so this is either a slow "
            "computation (re-run) or a PR that is no longer open. It is NOT a conflict.",
        }
    if state == "BEHIND":
        return {
            "verdict": "ESCALATE",
            "note": "The branch is behind base and this repo requires up-to-date "
            "branches. Updating it rewrites the branch — hand to the user.",
        }
    if state == "BLOCKED":
        return {
            "verdict": "ESCALATE",
            "note": "GitHub reports BLOCKED: branch protection is unsatisfied — a "
            "required approval, or a required check this gate cannot see.",
        }
    if state == "DRAFT":
        return {
            "verdict": "ESCALATE",
            "note": "The PR is still a draft. Mark it ready for review before merging.",
        }
    return {
        "verdict": "ESCALATE",
        "note": f'Unrecognised mergeStateStatus "{state}" — refusing to merge on a state '
        "this gate does not model. If GitHub added it, map it in decide_verdict().",
    }


def human_changes_requested(reviews: list, author: str) -> bool:
    """Is a HUMAN reviewer sitting in CHANGES_REQUESTED?

    Only a human blocks. A bot's CHANGES_REQUESTED is a review finding the loop
    classifies normally; treating it as a human block escalates the PR to a
    person forever and the loop can never merge.
    """
    latest: dict[str, dict] = {}
    for review in reviews or []:
        login = (review.get("author") or {}).get("login") or ""
        if login == author or is_bot(login):
            continue
        seen = latest.get(login)
        if seen is None or (review.get("submittedAt") or "") >= (seen.get("submittedAt") or ""):
            latest[login] = review
    return any(r.get("state") == "CHANGES_REQUESTED" for r in latest.values())


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: pr-state.py <PR#>\n")
        return EXIT_USAGE
    pr = sys.argv[1].strip().lstrip("#")
    # GraphQL's Int! and the output's int() both need a bare number, while `gh pr view` would
    # happily take a URL — so a URL got most of the way through, returned zero threads from the
    # GraphQL call, and died with a traceback at output time instead of saying what was wrong.
    if not pr.isdigit():
        sys.stderr.write(f"usage: pr-state.py <PR#> — expected a number, got {sys.argv[1]!r}\n")
        return EXIT_USAGE
    budget = int(os.environ.get("AUTO_PR_ROUND_BUDGET", "3"))
    review_workflow = os.environ.get("AUTO_PR_REVIEW_WORKFLOW", "PR Review")
    warnings: list[str] = []

    pr_json = gh_json("pr", "view", pr, "--json", PR_FIELDS)
    if not pr_json:
        sys.stderr.write(f"could not read PR #{pr}\n")
        return EXIT_TEMPFAIL

    # GitHub computes mergeability LAZILY: the first query on a PR whose merge
    # commit is not cached kicks off a background job and returns UNKNOWN.
    # Re-querying is the documented remedy — the request is itself what
    # schedules the computation. Bounded, and only while the PR is OPEN: GitHub
    # never computes it for a closed PR, so polling one just burns the delay.
    if pr_json.get("state") == "OPEN":
        for _ in range(3):
            if pr_json.get("mergeable") != "UNKNOWN":
                break
            time.sleep(2)
            # check=False so the `or pr_json` fallback is reachable: a blip DURING the
            # re-query should keep the state we already have, not end the run.
            pr_json = gh_json("pr", "view", pr, "--json", PR_FIELDS, check=False) or pr_json

    url = pr_json.get("url") or ""
    match = re.search(r"github\.com/([^/]+)/([^/]+)/", url)
    if not match:
        sys.stderr.write(f"could not parse owner/repo from {url!r}\n")
        return EXIT_BUG
    owner, repo = match.group(1), match.group(2)
    head_sha = pr_json.get("headRefOid") or ""
    head_ref = pr_json.get("headRefName") or ""
    base_ref = pr_json.get("baseRefName") or ""
    author = (pr_json.get("author") or {}).get("login") or ""

    # --- Round count: distinct shas a review has completed against -----------
    # "How many times has a reviewer actually looked" is the only honest
    # denominator. Commit count is not: several commits can land between two
    # reviews, and a dropped run means a commit nobody reviewed.
    #
    # The workflow NAME is repo-configurable, and getting it wrong is a SILENT
    # HANG: zero matching runs reads as "no review yet", so the verdict sticks
    # on WAIT_REVIEW forever while the PR is in fact fully reviewed. So fall
    # back to every pull_request run and say so. A conservative superset beats
    # a confident zero.
    run_fields = "headSha,conclusion,status,createdAt,updatedAt"
    runs = (
        gh_json(
            "run", "list", "--branch", head_ref, "--workflow", review_workflow,
            "--limit", "60", "--json", run_fields, default=[], check=False,
        )
        or []
    )
    if not runs:
        runs = (
            gh_json(
                "run", "list", "--branch", head_ref, "--event", "pull_request",
                "--limit", "60", "--json", run_fields + ",workflowName",
                default=[], check=False,
            )
            or []
        )
        seen_names = sorted({r.get("workflowName") or "" for r in runs} - {""})
        if not seen_names:
            warnings.append(
                f"No runs found for workflow '{review_workflow}' on this branch, and no "
                "pull_request runs either. Round count will read 0 and the verdict will "
                "sit on WAIT_REVIEW."
            )
        else:
            warnings.append(
                f"No runs found for workflow '{review_workflow}' on this branch; counted "
                f"all pull_request runs instead (saw: {', '.join(seen_names)}). Set "
                "AUTO_PR_REVIEW_WORKFLOW to the right name."
            )

    def succeeded(run: dict) -> bool:
        return run.get("status") == "completed" and run.get("conclusion") == "success"

    review_round = len({r.get("headSha") for r in runs if succeeded(r)})
    on_head = [r for r in runs if r.get("headSha") == head_sha]
    review_on_head = any(succeeded(r) for r in on_head)
    review_conclusion = on_head[0].get("conclusion") if on_head else None

    # A review that failed in under 90s is the documented installer flake, not
    # findings. Without this the agent reads WAIT_CHECKS and hunts for a defect
    # that does not exist.
    review_flake = False
    for run in on_head:
        if run.get("conclusion") != "failure":
            continue
        started, ended = parse_ts(run.get("createdAt")), parse_ts(run.get("updatedAt"))
        if started and ended and (ended - started).total_seconds() < 90:
            review_flake = True
    if review_flake:
        warnings.append(
            "Review run on head sha failed in <90s — almost certainly the installer "
            "flake, not findings. Run: gh run rerun --failed"
        )

    # --- Review threads ------------------------------------------------------
    # Paginated: a long PR really does exceed one page, and a truncated list
    # reports `blocking: 0` for findings it simply never fetched.
    # comments(first:50) because severity depends on the WHOLE conversation.
    query = """
      query($owner:String!, $repo:String!, $pr:Int!, $endCursor:String) {
        repository(owner:$owner, name:$repo) {
          pullRequest(number:$pr) {
            reviewThreads(first:100, after:$endCursor) {
              totalCount
              pageInfo { hasNextPage endCursor }
              nodes {
                id isResolved isOutdated path
                comments(first:50) {
                  totalCount
                  nodes { databaseId body line originalLine createdAt author { login } }
                }
              }
            }
          }
        }
      }"""
    # The ONE call whose failure must not degrade quietly. Every other `gh` here fails safe:
    # `gh pr view` bails, a failed `run list` only pushes toward WAIT_REVIEW, a failed
    # protection read only widens the gating set. Here an empty result would mean zero threads,
    # zero blocking findings, and a MERGE verdict on an unread review — so read the status and
    # refuse rather than emit a verdict. A hard exit costs one iteration of a self-paced loop;
    # a wrong merge cannot be taken back.
    threads_status, pages_raw = gh_run(
        "api", "graphql", "--paginate", "-f", f"query={query}",
        "-f", f"owner={owner}", "-f", f"repo={repo}", "-F", f"pr={pr}",
    )
    if threads_status != 0 or not pages_raw.strip():
        sys.stderr.write(
            "could not read the review threads (gh exit "
            f"{threads_status}) — refusing to emit a verdict on an unread review\n"
        )
        return EXIT_TEMPFAIL
    raw_threads: list[dict] = []
    total_threads = 0
    for line in pages_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            page = json.loads(line)
        except json.JSONDecodeError:
            continue
        node = (
            page.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("reviewThreads", {})
        )
        raw_threads.extend(node.get("nodes") or [])
        total_threads = max(total_threads, node.get("totalCount") or 0)

    if len(raw_threads) < total_threads:
        warnings.append(
            f"Fetched {len(raw_threads)} of {total_threads} review threads — pagination "
            "came up short. Findings may be missing from the gate."
        )
    truncated = sum(
        1
        for t in raw_threads
        if ((t.get("comments") or {}).get("totalCount") or 0)
        > len((t.get("comments") or {}).get("nodes") or [])
    )
    if truncated:
        warnings.append(
            f"{truncated} thread(s) have more than 50 comments; only the first 50 were "
            "read. Escalation detection may be stale on those."
        )

    me, identity_warning = resolve_self_login(raw_threads, author)
    if identity_warning:
        warnings.append(identity_warning)
    classified = [c for c in (classify_thread(t, author, me) for t in raw_threads) if c]
    by_severity: dict[str, list[dict]] = {"blocking": [], "nit": [], "unclassified": []}
    settled = 0
    for thread in classified:
        if thread["severity"] == "settled":
            settled += 1
        else:
            by_severity[thread["severity"]].append(thread)
    escalated = sum(1 for t in classified if t["escalated"])
    if escalated:
        warnings.append(
            f"{escalated} thread(s) have a reviewer comment newer than your reply — "
            "reclassified as unclassified. Reply again (with a marker); resolving alone "
            "will not clear them."
        )

    # --- Checks --------------------------------------------------------------
    # Gate on the branch-protection required list when it is readable. Without
    # it, any red OPTIONAL check (coverage bots, advisory scanners) blocks the
    # merge forever — the gate would be stricter than GitHub itself.
    required: set[str] = set()
    protection = gh_json(
        "api", f"repos/{owner}/{repo}/branches/{base_ref}/protection",
        default=None, check=False,
    )
    if isinstance(protection, dict):
        rsc = protection.get("required_status_checks") or {}
        required |= {c for c in (rsc.get("contexts") or []) if c}
        required |= {(c or {}).get("context") for c in (rsc.get("checks") or [])}
        required.discard(None)

    all_checks = []
    for check in pr_json.get("statusCheckRollup") or []:
        # statusCheckRollup is a union. A CheckRun has `status` + `conclusion`; a StatusContext
        # (the legacy commit-status API — Buildkite, CircleCI, Vercel) has only `state`, which
        # is where ITS pending lives. Defaulting a missing `status` to COMPLETED therefore read
        # a pending status context as green, and FAILURE/ERROR only worked by spelling
        # collision. Fold the two shapes into one before anything reads them.
        state = (check.get("state") or "").upper()
        status = (check.get("status") or "").upper()
        if not status:
            status = "PENDING" if state in ("PENDING", "EXPECTED") else "COMPLETED"
        all_checks.append(
            {
                "name": check.get("name") or check.get("context") or "check",
                "status": status,
                "conclusion": (check.get("conclusion") or state or "").upper(),
                # A StatusContext has no startedAt; createdAt is the nearest truth, and without
                # it the ">15 minutes pending" warning could never fire for these.
                "startedAt": check.get("startedAt") or check.get("createdAt"),
            }
        )
    gating = [c for c in all_checks if c["name"] in required] if required else all_checks
    failing = [c["name"] for c in gating if c["conclusion"] in FAILED_CONCLUSIONS]
    pending_list = [c for c in gating if c["status"] in PENDING_STATUSES]
    now = datetime.now(timezone.utc)
    pending_ages = [
        (now - ts).total_seconds() / 60
        for ts in (parse_ts(c["startedAt"]) for c in pending_list)
        if ts is not None
    ]
    oldest_pending = max(pending_ages) if pending_ages else None
    all_green = not failing and not pending_list

    if required and len(gating) < len(all_checks):
        warnings.append(
            f"Gating on {len(gating)} required check(s) of {len(all_checks)} present; "
            "non-required checks are reported but do not block."
        )
    if oldest_pending is not None and oldest_pending > 15:
        warnings.append(
            f"A gating check has been pending {int(oldest_pending)} minutes (>15). "
            "Consider surfacing to the user."
        )

    # --- Unreviewable PR -----------------------------------------------------
    # The review workflow's credentials are validated against the BASE branch,
    # so a PR that edits that workflow gets a 401, a startup failure, or a
    # success with no comment — indistinguishable from a clean review. Merging
    # on that signal would merge unreviewed code.
    unreviewable = any(
        REVIEW_WORKFLOW_PATH.search(f.get("path") or f.get("filename") or "")
        for f in (pr_json.get("files") or [])
    )
    if unreviewable:
        warnings.append(
            "This PR edits the review workflow itself — its review result is not "
            "trustworthy (401 / startup failure / silent success all look alike). "
            "Hand to the user."
        )

    mergeable = pr_json.get("mergeable") or "UNKNOWN"
    merge_state = pr_json.get("mergeStateStatus") or "UNKNOWN"
    human_cr = human_changes_requested(pr_json.get("reviews") or [], author)

    decision = decide_verdict(
        {
            "blocking": len(by_severity["blocking"]),
            "unclassified": len(by_severity["unclassified"]),
            "all_green": all_green,
            "failing": len(failing),
            "review_on_head": review_on_head,
            "human_cr": human_cr,
            "unreviewable": unreviewable,
            "round": review_round,
            "budget": budget,
            "mergeable": mergeable,
            "merge_state": merge_state,
        }
    )
    if decision["note"]:
        warnings.append(decision["note"])

    json.dump(
        {
            "pr": int(pr),
            "head_sha": head_sha,
            "round": review_round,
            "round_budget": budget,
            "warnings": warnings,
            "review_check": {
                "workflow": review_workflow,
                "conclusion": review_conclusion,
                "on_head": review_on_head,
                "flake_suspected": review_flake,
            },
            "threads": by_severity,
            "counts": {
                "blocking": len(by_severity["blocking"]),
                "nit": len(by_severity["nit"]),
                "unclassified": len(by_severity["unclassified"]),
                "settled": settled,
                "escalated": escalated,
                "total_threads": total_threads,
            },
            "checks": {
                "all_green": all_green,
                "failing": failing,
                "pending": len(pending_list),
                "oldest_pending_minutes": oldest_pending,
                "gated_on_required_list": bool(required),
            },
            "mergeable": mergeable,
            "merge_state": merge_state,
            "human_changes_requested": human_cr,
            "unreviewable": unreviewable,
            "verdict": decision["verdict"],
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
