#!/usr/bin/env bash
# classify.test.sh — drives classify_thread() and resolve_self_login() in pr-state.py, the
# EXACT functions the gate runs.
#
# Severity classification is the half of the gate that decides whether the loop acts at all, and
# every case below maps to a way it could wrongly merge or wrongly spin. The self-originated
# ones are here because that shape regressed twice: a filter meant to stop a self-only thread
# sitting `unclassified` forever swallowed the operator's own [BLOCKING] instead.
#
# Runs on python3 alone — no `jq`, which the agent's sandbox does not have.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pass=0; fail=0

# case <label> <expected severity, or DROPPED> <thread json> [me] [author]
case_() {
  local label="$1" want="$2" thread="$3" me="${4:-agent}" author="${5:-alice}"
  local got
  got="$(SCRIPT_DIR="$SCRIPT_DIR" THREAD="$thread" ME="$me" AUTHOR="$author" python3 - <<'PY'
import importlib.util, json, os
spec = importlib.util.spec_from_file_location(
    "pr_state", os.path.join(os.environ["SCRIPT_DIR"], "pr-state.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
out = mod.classify_thread(json.loads(os.environ["THREAD"]), os.environ["AUTHOR"], os.environ["ME"])
print("DROPPED" if out is None else out["severity"])
PY
)"
  if [ "$got" = "$want" ]; then pass=$((pass+1)); printf '  ok   %s\n' "$label"
  else fail=$((fail+1)); printf '  FAIL %s\n         want=%s got=%s\n' "$label" "$want" "$got"; fi
}

# comment helper: {login, body, createdAt}
T() { printf '%s' "$1"; }

echo "-- ordinary reviewer threads --"
case_ "plain reviewer comment -> unclassified" unclassified '{
  "id":"T1","isResolved":false,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":1,
  "nodes":[{"databaseId":1,"body":"this looks off","createdAt":"2026-01-01T00:00:00Z","author":{"login":"claude"}}]}}'

case_ "explicit [BLOCKING] -> blocking" blocking '{
  "id":"T2","isResolved":false,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":1,
  "nodes":[{"databaseId":1,"body":"[BLOCKING] drops the last row","createdAt":"2026-01-01T00:00:00Z","author":{"login":"claude"}}]}}'

case_ "a prose file is structurally a nit" nit '{
  "id":"T3","isResolved":false,"isOutdated":false,"path":"docs/x.md","comments":{"totalCount":1,
  "nodes":[{"databaseId":1,"body":"stale sentence","createdAt":"2026-01-01T00:00:00Z","author":{"login":"claude"}}]}}'

case_ "our marker settles it" settled '{
  "id":"T4","isResolved":false,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":2,
  "nodes":[{"databaseId":1,"body":"[BLOCKING] drops the last row","createdAt":"2026-01-01T00:00:00Z","author":{"login":"claude"}},
           {"databaseId":2,"body":"Applied in abc123. <!-- auto-pr:fixed -->","createdAt":"2026-01-01T01:00:00Z","author":{"login":"agent"}}]}}'

case_ "a reviewer speaking after us reopens it" unclassified '{
  "id":"T5","isResolved":true,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":3,
  "nodes":[{"databaseId":1,"body":"[NIT] naming","createdAt":"2026-01-01T00:00:00Z","author":{"login":"claude"}},
           {"databaseId":2,"body":"Noted. <!-- auto-pr:nit -->","createdAt":"2026-01-01T01:00:00Z","author":{"login":"agent"}},
           {"databaseId":3,"body":"actually this drops data","createdAt":"2026-01-01T02:00:00Z","author":{"login":"claude"}}]}}'

case_ "a thread the PR AUTHOR opened is dropped" DROPPED '{
  "id":"T6","isResolved":false,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":1,
  "nodes":[{"databaseId":1,"body":"note to self","createdAt":"2026-01-01T00:00:00Z","author":{"login":"alice"}}]}}'

echo "-- self-originated threads (regressed twice; see the comment in classify_thread) --"
# The operator leaves an inline [BLOCKING] and then types /auto-pr, so the thread has exactly
# one comment and nobody has answered it yet. Both previous filters dropped this and merged.
case_ "self-originated, UNANSWERED, [BLOCKING] -> blocking" blocking '{
  "id":"S1","isResolved":false,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":1,
  "nodes":[{"databaseId":1,"body":"[BLOCKING] this drops the last row","createdAt":"2026-01-01T00:00:00Z","author":{"login":"agent"}}]}}'

case_ "self-originated, UNANSWERED, unmarked -> unclassified" unclassified '{
  "id":"S2","isResolved":false,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":1,
  "nodes":[{"databaseId":1,"body":"this reads oddly","createdAt":"2026-01-01T00:00:00Z","author":{"login":"agent"}}]}}'

# What ends a self-only thread is US answering — a marker, or a resolve. Not somebody arriving.
case_ "self-originated, we answered with a marker -> settled" settled '{
  "id":"S3","isResolved":false,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":2,
  "nodes":[{"databaseId":1,"body":"[BLOCKING] this drops the last row","createdAt":"2026-01-01T00:00:00Z","author":{"login":"agent"}},
           {"databaseId":2,"body":"Applied in abc123. <!-- auto-pr:fixed -->","createdAt":"2026-01-01T01:00:00Z","author":{"login":"agent"}}]}}'

case_ "self-originated, resolved -> settled" settled '{
  "id":"S4","isResolved":true,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":1,
  "nodes":[{"databaseId":1,"body":"[BLOCKING] this drops the last row","createdAt":"2026-01-01T00:00:00Z","author":{"login":"agent"}}]}}'

# The App-token deployment: the reviewing bot and the replying account share a login, so
# EVERY thread is self-originated. It must still be classified.
case_ "shared login: reviewer==us, [BLOCKING] -> blocking" blocking '{
  "id":"S5","isResolved":false,"isOutdated":false,"path":"src/a.py","comments":{"totalCount":1,
  "nodes":[{"databaseId":1,"body":"[BLOCKING] race on the retry path","createdAt":"2026-01-01T00:00:00Z","author":{"login":"astralform-agent[bot]"}}]}}' \
  "astralform-agent[bot]"

echo "-- identity resolution --"
identity() {
  local label="$1" want="$2" threads="$3" override="${4:-}"
  local got
  got="$(SCRIPT_DIR="$SCRIPT_DIR" THREADS="$threads" AUTO_PR_SELF_LOGIN="$override" python3 - <<'PY'
import importlib.util, json, os
spec = importlib.util.spec_from_file_location(
    "pr_state", os.path.join(os.environ["SCRIPT_DIR"], "pr-state.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
# Keep the test offline: `gh api user` must never be reached for these cases.
mod.gh_run = lambda *a: (1, "")
login, warning = mod.resolve_self_login(json.loads(os.environ["THREADS"]), "alice")
print(f"{login}|{'WARN' if warning else 'quiet'}")
PY
)"
  if [ "$got" = "$want" ]; then pass=$((pass+1)); printf '  ok   %s\n' "$label"
  else fail=$((fail+1)); printf '  FAIL %s\n         want=%s got=%s\n' "$label" "$want" "$got"; fi
}

MARKED='[{"comments":{"nodes":[{"body":"Noted. <!-- auto-pr:nit -->","author":{"login":"agent"}}]}}]'

identity "a marker outranks the override, and says so" "agent|WARN" "$MARKED" "someone-else"
identity "a marker agreeing with the override is quiet" "agent|quiet" "$MARKED" "agent"
identity "no marker: the override wins"                "boto|quiet"  '[]' "boto"
identity "nothing at all: the author, with a warning"  "alice|WARN"  '[]' ""

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
