#!/usr/bin/env bash
# gate.sh --repo-dir <dir> [--budget <seconds>]
#
# Run the repository's own lint and test commands, and say plainly whether they
# passed. Detects the stack rather than assuming one.
#
# Exit codes are the interface:
#   0  at least one real check ran and everything that ran passed
#   1  a check failed, or one exceeded the budget
#   2  nothing to run — no recognised manifest, none that defines a check, or
#      none whose toolchain is installed in this sandbox
#   3  EGRESS — a dependency install could not reach a host
#  64  usage error — kept OFF 2, so a caller that reads 2 as "this repo has no
#      gate" cannot mistake a mistyped argument for a clean verdict
#
# Two distinctions this script exists to make, because getting either wrong
# produces a confident wrong answer:
#
#   * A failing gate (1) vs an unreachable host (3). This sandbox reaches
#     github.com and whatever the agent's network policy allows, nothing else.
#     Every package manager exits 1 for both, so the OUTPUT is what separates
#     them. Reporting an egress wall as a red test suite sends the caller
#     hunting for a bug that does not exist.
#   * A check that RAN vs a manifest that merely EXISTS. Installing dependencies
#     proves nothing about the code. Only lint, typecheck and test count toward
#     PASS, so a repo that defines none of them exits 2 rather than handing back
#     a green light nothing earned.

set -euo pipefail

die() { echo "gate.sh: $*" >&2; exit 64; }

REPO_DIR=""
BUDGET=240
while [ $# -gt 0 ]; do
  case "$1" in
    --repo-dir) REPO_DIR="${2:-}"; shift 2 ;;
    --budget)   BUDGET="${2:-}"; shift 2 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[ -n "$REPO_DIR" ] || die "usage: gate.sh --repo-dir <dir> [--budget <seconds>]"
[ -d "$REPO_DIR" ] || die "no such directory: $REPO_DIR"
cd "$REPO_DIR"

OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT

# How many real checks executed. Incremented by run_check only, never by setup.
CHECKS=0

egress_wall() {
  grep -qiE "could not resolve host|temporary failure in name resolution|getaddrinfo|network is unreachable|connection refused|EAI_AGAIN|ETIMEDOUT|tunneling socket could not be established" "$1"
}

# The host a failed fetch reached for. Each pattern is tried on its own: a
# pipeline ending in sed exits 0 on empty input, so chaining them with `||` made
# the second pattern unreachable. `|| true` guards SIGPIPE from head under
# `set -o pipefail`, which is a 141 that says nothing about the match.
blocked_host() {
  local h
  h="$( { grep -oiE "https?://[a-z0-9.-]+" "$1" || true; } | head -1 | sed -E 's#https?://##')"
  [ -n "$h" ] || h="$( { grep -oiE "host: ?[a-z0-9.-]+" "$1" || true; } | head -1 | sed -E 's/host: ?//I')"
  printf '%s' "$h"
}

# Runs one command and classifies its failure. `code` is captured INSIDE the
# condition: `$?` after an if-without-else is the status of the compound (zero
# when no branch ran), not of the command — reading it afterwards silently loses
# timeout's 124 and turns "too slow" into "your tests are red".
_exec() {
  local label="$1"; shift
  local code=0
  echo "gate.sh: $label — $*" >&2
  if timeout "$BUDGET" "$@" >"$OUT" 2>&1; then
    tail -5 "$OUT" >&2
    return 0
  else
    code=$?
  fi
  tail -30 "$OUT" >&2
  if egress_wall "$OUT"; then
    local host; host="$(blocked_host "$OUT")"
    echo "EGRESS: allow ${host:-the host in the output above} on this agent"
    exit 3
  fi
  if [ "$code" -eq 124 ]; then
    echo "TIMEOUT: $label exceeded ${BUDGET}s — run it with capsule.proc.run_background and poll"
    exit 1
  fi
  echo "FAIL: $label"
  exit 1
}

# Setup: needed for the checks to run, but never evidence on its own.
run_setup() { _exec "$@"; }

# A real check. Only these make PASS possible.
run_check() { _exec "$@"; CHECKS=$((CHECKS + 1)); }

if [ -f package.json ]; then
  # A missing toolchain is not a red gate: without the manager this repo's
  # lockfile names, `npm ci` would return 127 and print FAIL: install, telling
  # the caller the repository is broken when only the sandbox is unequipped.
  #
  # This SKIPS the block rather than exiting, because a repo can carry both a
  # package.json and a pyproject.toml — exiting here would silently deny the
  # Python gate its turn.
  JS_MANAGER=""
  if [ -f pnpm-lock.yaml ]; then
    command -v pnpm >/dev/null 2>&1 && JS_MANAGER="pnpm"
  elif [ -f yarn.lock ]; then
    command -v yarn >/dev/null 2>&1 && JS_MANAGER="yarn"
  elif command -v npm >/dev/null 2>&1; then
    JS_MANAGER="npm"
  fi

  if [ -z "$JS_MANAGER" ]; then
    echo "gate.sh: package.json found but its package manager is not installed here — skipping the JS checks" >&2
  else
    case "$JS_MANAGER" in
      pnpm) run_setup "install" pnpm install --frozen-lockfile ;;
      yarn) run_setup "install" yarn install --frozen-lockfile ;;
      npm)  if [ -f package-lock.json ]; then run_setup "install" npm ci
            else run_setup "install" npm install
            fi ;;
    esac
    # Only scripts the repo actually defines; a missing one is not a failure.
    has_script() { node -e "process.exit(require('./package.json').scripts?.['$1']?0:1)" 2>/dev/null; }
    if has_script lint; then run_check "lint" "$JS_MANAGER" run lint; fi
    if has_script typecheck; then run_check "typecheck" "$JS_MANAGER" run typecheck; fi
    if has_script test; then run_check "test" "$JS_MANAGER" run test; fi
  fi
fi

if [ -f pyproject.toml ]; then
  if command -v uv >/dev/null 2>&1; then
    run_setup "install" uv sync
    if grep -q "ruff" pyproject.toml; then run_check "lint" uv run ruff check .; fi
    run_check "test" uv run pytest -q
  else
    # No uv means nothing was installed, so only tools already on PATH can run.
    # If neither is present, CHECKS stays 0 and the exit below says so rather
    # than reporting a gate that never executed as green.
    if command -v ruff >/dev/null 2>&1; then run_check "lint" ruff check .; fi
    if command -v pytest >/dev/null 2>&1; then run_check "test" pytest -q; fi
  fi
fi

if [ "$CHECKS" -eq 0 ] && [ -f Makefile ]; then
  if grep -qE "^test:" Makefile; then run_check "test" make test; fi
fi

if [ "$CHECKS" -eq 0 ]; then
  echo "NO GATE: nothing to run — no lint, typecheck or test was found to execute"
  exit 2
fi

echo "PASS: the repository's own checks are green ($CHECKS ran)"
