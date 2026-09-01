#!/usr/bin/env bash
# new-worktree.sh <slug> [prefix]
#
# Create an isolated worktree branched off a freshly-fetched origin/<default>,
# for the auto-fix loop. Branching off the REMOTE ref (not local) sidesteps the
# "local default is ahead of origin" trap that makes the pre-PR diff gate fire
# with commits the fix never introduced.
#
# Guards (all refuse rather than guess):
#   - not a git repo
#   - malformed slug
#   - branch already exists (local or remote)
#   - worktree path already exists
#   - no origin remote
#
# Warns (non-fatal) when the local default branch is ahead of origin's, since
# that is the user's unpushed work and this script deliberately does not build
# on it.
#
# Output (machine-readable, stdout):
#   WORKTREE=/abs/path/to/worktree
#   BRANCH=fix/some-slug
#   BASE=<sha of origin/default>
#   DEFAULT=main
#
# Diagnostics go to stderr. Exit codes: 0 ok, 2 usage, 3 guard tripped.

set -euo pipefail

die()  { printf 'new-worktree: %s\n' "$1" >&2; exit "${2:-3}"; }
warn() { printf 'new-worktree: warning: %s\n' "$*" >&2; }

[ $# -ge 1 ] || die "usage: new-worktree.sh <slug> [prefix]   (prefix: fix|feat|chore|docs|test, default fix)" 2

slug="$1"
prefix="${2:-fix}"

case "$slug" in
  *[!a-z0-9-]* | -* | *- | "") die "slug must be lowercase alphanumeric + inner hyphens, got: '$slug'" ;;
esac
case "$prefix" in
  fix|feat|chore|docs|test) ;;
  *) die "prefix must be one of: fix feat chore docs test (got '$prefix')" ;;
esac

git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"

# Operate from the main worktree's toplevel, so ../<name> is predictable even
# when this is invoked from inside another worktree.
toplevel="$(git rev-parse --show-toplevel)"
common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [ -n "$common" ]; then
  main_root="$(dirname "$common")"
  [ -d "$main_root" ] && toplevel="$main_root"
fi
cd "$toplevel"

git remote get-url origin >/dev/null 2>&1 || die "no 'origin' remote configured"

git fetch --prune --quiet origin || die "git fetch failed"

# Resolve the default branch: origin/HEAD, then common names.
default=""
if ref="$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null)"; then
  default="${ref#refs/remotes/origin/}"
else
  # origin/HEAD is often unset on fresh clones; ask the remote, then guess.
  default="$(git remote show origin 2>/dev/null | awk '/HEAD branch:/ {print $NF; exit}')" || true
  if [ -z "$default" ] || [ "$default" = "(unknown)" ]; then
    for c in main master trunk develop; do
      if git show-ref --verify --quiet "refs/remotes/origin/$c"; then default="$c"; break; fi
    done
  fi
fi
[ -n "$default" ] || die "could not determine the default branch on origin"
git show-ref --verify --quiet "refs/remotes/origin/$default" \
  || die "origin/$default does not exist after fetch"

branch="$prefix/$slug"
git show-ref --verify --quiet "refs/heads/$branch"           && die "branch already exists locally: $branch"
git show-ref --verify --quiet "refs/remotes/origin/$branch"  && die "branch already exists on origin: $branch"

repo="$(basename "$toplevel")"
worktree="$(dirname "$toplevel")/${repo}-${slug}"
[ -e "$worktree" ] && die "path already exists: $worktree"

# Non-fatal: the user's unpushed default-branch work is intentionally not a base.
if git show-ref --verify --quiet "refs/heads/$default"; then
  ahead="$(git rev-list --count "origin/$default..$default" 2>/dev/null || echo 0)"
  if [ "${ahead:-0}" -gt 0 ]; then
    warn "local $default is $ahead commit(s) ahead of origin/$default; branching off origin/$default, so those commits are NOT in this worktree"
  fi
fi

git worktree add --quiet -b "$branch" "$worktree" "origin/$default" \
  || die "git worktree add failed"

base="$(git rev-parse "origin/$default")"

printf 'WORKTREE=%s\n' "$worktree"
printf 'BRANCH=%s\n'   "$branch"
printf 'BASE=%s\n'     "$base"
printf 'DEFAULT=%s\n'  "$default"
