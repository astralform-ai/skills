#!/usr/bin/env bash
# gate.sh --repo-dir <dir> [--budget <seconds>]
#
# Run the repository's own lint and test commands, and say plainly whether they
# passed. Detects the stack rather than assuming one.
#
# Exit codes are the interface:
#   0  everything detected passed
#   1  a check failed — the repo's own gate is red
#   2  nothing to run (no recognised project manifest)
#   3  EGRESS — a dependency install could not reach a host
#
# 3 is separate on purpose. This sandbox reaches github.com and whatever the
# agent's network policy allows, and nothing else. An install that cannot resolve
# a host is not a broken repository and must not be reported as one — the caller
# stops and names the host to allow, rather than opening a PR whose tests never
# ran.

set -euo pipefail

die() { echo "gate.sh: $*" >&2; exit 2; }

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

# An install that fails because a host is unreachable, told apart from one that
# fails because the code is wrong. Checked against the OUTPUT, not the exit code,
# because every package manager exits 1 for both.
egress_wall() {
  grep -qiE "could not resolve host|temporary failure in name resolution|getaddrinfo|network is unreachable|connection refused|EAI_AGAIN|ETIMEDOUT|tunneling socket could not be established" "$1"
}

# The host a failed fetch was reaching for, so the caller can name it.
blocked_host() {
  grep -oiE "https?://[a-z0-9.-]+" "$1" | head -1 | sed -E 's#https?://##' ||
    grep -oiE "host: ?[a-z0-9.-]+" "$1" | head -1 | sed -E 's/host: ?//'
}

run() {
  local label="$1"; shift
  echo "gate.sh: $label — $*" >&2
  if timeout "$BUDGET" "$@" >"$OUT" 2>&1; then
    tail -5 "$OUT" >&2
    return 0
  fi
  local code=$?
  tail -30 "$OUT" >&2
  if egress_wall "$OUT"; then
    local host; host="$(blocked_host "$OUT")"
    echo "EGRESS: allow ${host:-the host above} on this agent"
    exit 3
  fi
  if [ "$code" -eq 124 ]; then
    echo "TIMEOUT: $label exceeded ${BUDGET}s — run it in the background and poll"
    exit 1
  fi
  echo "FAIL: $label"
  exit 1
}

RAN=0

if [ -f package.json ]; then
  RAN=1
  if [ -f package-lock.json ]; then run "install" npm ci
  elif [ -f pnpm-lock.yaml ]; then run "install" pnpm install --frozen-lockfile
  elif [ -f yarn.lock ]; then run "install" yarn install --frozen-lockfile
  else run "install" npm install
  fi
  # Only scripts the repo actually defines; asking for a missing one is not a failure.
  has_script() { node -e "process.exit(require('./package.json').scripts?.['$1']?0:1)" 2>/dev/null; }
  has_script lint && run "lint" npm run lint
  has_script typecheck && run "typecheck" npm run typecheck
  has_script test && run "test" npm test
fi

if [ -f pyproject.toml ]; then
  RAN=1
  if command -v uv >/dev/null 2>&1; then
    run "install" uv sync
    grep -q '"\?ruff"\?' pyproject.toml && run "lint" uv run ruff check .
    run "test" uv run pytest -q
  else
    command -v ruff >/dev/null 2>&1 && run "lint" ruff check .
    command -v pytest >/dev/null 2>&1 && run "test" pytest -q
  fi
fi

if [ "$RAN" -eq 0 ] && [ -f Makefile ]; then
  grep -qE "^test:" Makefile && { RAN=1; run "test" make test; }
fi

if [ "$RAN" -eq 0 ]; then
  echo "NO GATE: no package.json, pyproject.toml or Makefile test target found"
  exit 2
fi

echo "PASS: the repository's own checks are green"
