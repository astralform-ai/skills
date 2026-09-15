#!/usr/bin/env bash
# color.test.sh — drives gh_run()/gh_json() in pr-state.py against ANSI-laced gh
# output and a forced-color sandbox env.
#
# gh colors PIPED output when the environment forces it (FORCE_COLOR /
# CLICOLOR_FORCE, both set in agent sandboxes). The gate passed that colored JSON
# straight into json.loads, which failed, and main() reported a false
# "could not read PR" (exit 75) with healthy permissions. These cases assert the
# gate parses gh output ANSI-free AND hands gh a sanitized child env.
#
# NOTE: heredoc bodies nested in $(...) must not contain apostrophes — bash 3.2
# (still the macOS default) mis-parses them. The existing suites follow the same
# rule.
#
# Runs on python3 alone — no `jq`, which the agent's sandbox does not have.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pass=0; fail=0

# check <label> <want> <got>
check() {
  local label="$1" want="$2" got="$3"
  if [ "$got" = "$want" ]; then pass=$((pass+1)); printf '  ok   %s\n' "$label"
  else fail=$((fail+1)); printf '  FAIL %s\n         want=%s got=%s\n' "$label" "$want" "$got"; fi
}

# ANSI-laced JSON exactly like gh emits under FORCE_COLOR=1:
#   \x1b[1;37m{\x1b[m\n  \x1b[1;34m"state"\x1b[m\x1b[1;37m:\x1b[m \x1b[32m"MERGED"\x1b[m\n}
COLOR_JSON=$'\x1b[1;37m{\x1b[m\n  \x1b[1;34m"state"\x1b[m\x1b[1;37m:\x1b[m \x1b[32m"MERGED"\x1b[m\x1b[1;37m,\x1b[m\n  \x1b[1;34m"mergeable"\x1b[m\x1b[1;37m:\x1b[m \x1b[32m"MERGEABLE"\x1b[m\n\x1b[1;37m}\x1b[m\x1b[m'

echo "-- gh_json parses gh output even when ANSI-laced --"

# runs python, importing the REAL pr-state.py, faking subprocess.run to return
# COLOR_JSON from gh, and printing what gh_json() returns as a single line.
ansi_json() {
  local label="$1" expected="$2"
  local got
  got="$(SCRIPT_DIR="$SCRIPT_DIR" COLOR_JSON="$COLOR_JSON" python3 - <<'PY'
import importlib.util, json, os
spec = importlib.util.spec_from_file_location(
    "pr_state", os.path.join(os.environ["SCRIPT_DIR"], "pr-state.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FakeProc:
    def __init__(self, stdout, stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

# Record the child env gh_run passes to subprocess, so the sanitization case can
# assert on it.
seen_env = {}
def fake_run(cmd, capture_output=True, text=True, timeout=120, env=None):
    seen_env.update(env or {})
    return FakeProc(stdout=os.environ["COLOR_JSON"])

mod.subprocess.run = fake_run
parsed = mod.gh_json("pr", "view", "1", "--json", "state,mergeable")
print(json.dumps(parsed, sort_keys=True))
print("ENV_NC=" + ("1" if seen_env.get("NO_COLOR") else "0"), end=" ")
print("ENV_FC=" + ("1" if "FORCE_COLOR" in seen_env else "0"), end=" ")
print("ENV_CC=" + ("1" if "CLICOLOR_FORCE" in seen_env else "0"))
PY
)"
  local got_line
  got_line="$(printf '%s\n' "$got" | head -1)"
  check "$label (parses ANSI-laced JSON)" "$expected" "$got_line"
}

ansi_json "gh_json returns the object, not a false 'could not read' None" \
  '{"mergeable": "MERGEABLE", "state": "MERGED"}'

echo "-- gh_run hands gh a sanitized child env even when the sandbox forces color --"

env_sanitized() {
  local got
  got="$(SCRIPT_DIR="$SCRIPT_DIR" COLOR_JSON="$COLOR_JSON" python3 - <<'PY'
import importlib.util, os
spec = importlib.util.spec_from_file_location(
    "pr_state", os.path.join(os.environ["SCRIPT_DIR"], "pr-state.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Simulate the sandbox: color forced on TTY-less output.
os.environ["FORCE_COLOR"] = "1"
os.environ["CLICOLOR_FORCE"] = "1"

class FakeProc:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

seen_env = {}
def fake_run(cmd, capture_output=True, text=True, timeout=120, env=None):
    seen_env.update(env or {})
    return FakeProc(stdout="{}")

mod.subprocess.run = fake_run
code, out = mod.gh_run("pr", "view", "1", "--json", "state")
assert code == 0 and out == "{}", (code, out)
# Only the gh child env is asserted here; the gate env keeps the sandbox flags.
print("NC=" + ("1" if seen_env.get("NO_COLOR") == "1" else "0"), end=" ")
print("FC_REMOVED=" + ("1" if "FORCE_COLOR" not in seen_env else "0"), end=" ")
print("CC_REMOVED=" + ("1" if "CLICOLOR_FORCE" not in seen_env else "0"))
PY
)"
  check "NO_COLOR=1 in the gh child env" "$(printf '  %s' 'NC=1 FC_REMOVED=1 CC_REMOVED=1')" "$(printf '  %s' "$got")"
}

env_sanitized

echo "-- gh_run strips ANSI from a failing gh's stderr before printing it --"

stderr_clean() {
  local got
  got="$(SCRIPT_DIR="$SCRIPT_DIR" python3 - <<'PY'
import importlib.util, io, os, sys
spec = importlib.util.spec_from_file_location(
    "pr_state", os.path.join(os.environ["SCRIPT_DIR"], "pr-state.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FakeProc:
    def __init__(self, stdout="", stderr="", returncode=1):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

def fake_run(cmd, capture_output=True, text=True, timeout=120, env=None):
    return FakeProc(stdout="", stderr="\x1b[31merror: boom\x1b[m", returncode=1)

mod.subprocess.run = fake_run
buf = io.StringIO()
old = sys.stderr
sys.stderr = buf
try:
    code, out = mod.gh_run("api", "x")
finally:
    sys.stderr = old
print("code=%d stderr_has_ansi=%s" % (code, "1" if "\x1b" in buf.getvalue() else "0"))
PY
)"
  check "failing gh stderr is ANSI-free" "$(printf '  %s' 'code=1 stderr_has_ansi=0')" "$(printf '  %s' "$got")"
}

stderr_clean

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
