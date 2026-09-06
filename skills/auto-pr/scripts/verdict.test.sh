#!/usr/bin/env bash
# verdict.test.sh — drives decide_verdict() in pr-state.py, the EXACT function
# the gate runs. A copied-into-the-test version would drift and go green while
# production was broken.
#
# Each case maps to a way the gate could wrongly merge, wrongly hang, or wrongly
# escalate. A false ESCALATE is not harmless: it stops an otherwise-mergeable PR
# and hands the user a non-problem, which is how a daily driver loses trust.
#
# Runs on python3 alone — no `jq`, which the agent's sandbox does not have.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pass=0; fail=0

# A PR with nothing wrong: no findings, green, reviewed, budget spare.
HEALTHY='{"blocking":0,"unclassified":0,"all_green":true,"failing":0,"review_on_head":true,
          "human_cr":false,"unreviewable":false,"round":1,"budget":3,
          "mergeable":"MERGEABLE","merge_state":"CLEAN"}'

# verdict <label> <expected> <json-overrides>
verdict() {
  local label="$1" want="$2" over="${3-}"
  [ -n "$over" ] || over='{}'
  local got
  got="$(SCRIPT_DIR="$SCRIPT_DIR" HEALTHY="$HEALTHY" OVER="$over" python3 - <<'PY'
import importlib.util, json, os
spec = importlib.util.spec_from_file_location(
    "pr_state", os.path.join(os.environ["SCRIPT_DIR"], "pr-state.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
state = json.loads(os.environ["HEALTHY"])
state.update(json.loads(os.environ["OVER"]))
print(mod.decide_verdict(state)["verdict"])
PY
)"
  if [ "$got" = "$want" ]; then pass=$((pass+1)); printf '  ok   %s\n' "$label"
  else fail=$((fail+1)); printf '  FAIL %s\n         want=%s got=%s\n' "$label" "$want" "$got"; fi
}

echo "-- the gate's own findings drive the verdict --"
verdict "healthy PR merges"                  MERGE
verdict "an unclassified thread -> CLASSIFY" CLASSIFY     '{"unclassified":1}'
verdict "a blocking finding -> FIX_BLOCKING" FIX_BLOCKING '{"blocking":1}'
verdict "blocking outranks red checks"       FIX_BLOCKING '{"blocking":1,"all_green":false}'
verdict "red checks -> WAIT_CHECKS"          WAIT_CHECKS  '{"all_green":false,"failing":1}'
verdict "no review on head -> WAIT_REVIEW"   WAIT_REVIEW  '{"review_on_head":false}'

echo "-- states that genuinely need a human --"
verdict "conflict -> ESCALATE"                ESCALATE '{"mergeable":"CONFLICTING","merge_state":"DIRTY"}'
verdict "human CHANGES_REQUESTED -> ESCALATE" ESCALATE '{"human_cr":true}'
verdict "unreviewable PR -> ESCALATE"         ESCALATE '{"unreviewable":true}'
verdict "budget spent WITH blocking open"     ESCALATE '{"round":3,"blocking":1}'
verdict "budget spent with a check still RED"  ESCALATE '{"round":3,"all_green":false,"failing":1}'
verdict "branch BEHIND base -> ESCALATE"      ESCALATE '{"merge_state":"BEHIND"}'
verdict "branch protection BLOCKED"           ESCALATE '{"merge_state":"BLOCKED"}'
verdict "draft PR -> ESCALATE"                ESCALATE '{"merge_state":"DRAFT"}'
verdict "a state we do not model -> ESCALATE" ESCALATE '{"merge_state":"SOME_NEW_STATE"}'

echo "-- transient / non-gating states must NOT escalate --"
verdict "mergeability not yet computed -> WAIT"   WAIT_CHECKS '{"mergeable":"UNKNOWN","merge_state":"UNKNOWN"}'
verdict "merge_state UNKNOWN alone -> WAIT"       WAIT_CHECKS '{"merge_state":"UNKNOWN"}'
verdict "UNSTABLE w/ required set green -> MERGE" MERGE       '{"merge_state":"UNSTABLE"}'
verdict "HAS_HOOKS is mergeable -> MERGE"         MERGE       '{"merge_state":"HAS_HOOKS"}'
verdict "budget spent but nothing blocking"       MERGE       '{"round":3,"blocking":0}'
verdict "budget spent, a check merely RUNNING"    WAIT_CHECKS '{"round":3,"all_green":false,"failing":0}'

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
