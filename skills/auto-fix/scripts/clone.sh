#!/usr/bin/env bash
# clone.sh <owner/repo> <branch>
#
# Put a working clone of the task's repository in the sandbox, on a new branch.
#
# Four things this does that a bare `git clone` does not:
#
#   1. `gh auth setup-git` first, so git authenticates through gh's credential
#      helper using this run's token. No token ever appears in a remote URL,
#      which matters because a failed git command prints the URL it tried.
#   2. Clones SHALLOW and single-branch. The sandbox has ~6.9 GB free and a full
#      history plus dependencies can exhaust it.
#   3. Clones into ./work under the sandbox's WORKING DIRECTORY — not $HOME.
#      Probed on code-interpreter-v1: the kernel's cwd is /home/user while $HOME
#      is /root, so "$HOME/work" would put the clone in a different tree from
#      everything else and depend on who the process is.
#      Also not /tmp, which is RAM carved out of the 4 GB, and not /workspace,
#      which is a network mount that is slow and unreliable for git objects.
#   4. Sets a commit identity, because the sandbox has none and `git commit`
#      fails without one.
#
# Prints REPO_DIR= and BRANCH= for the caller to read. Refuses rather than
# guesses: every failure below exits non-zero with a reason on stderr.

set -euo pipefail

die() { echo "clone.sh: $*" >&2; exit 1; }

[ $# -eq 2 ] || die "usage: clone.sh <owner/repo> <branch>"
REPO="$1"
BRANCH="$2"

case "$REPO" in
  */*) : ;;
  *) die "repository must be owner/repo, got: $REPO" ;;
esac
case "$REPO" in
  *..*|/*|~*) die "refusing a repository name with path traversal: $REPO" ;;
esac
case "$BRANCH" in
  ""|*..*|*" "*|/*|-*) die "refusing an unsafe branch name: $BRANCH" ;;
esac

command -v gh >/dev/null 2>&1 || die "gh is not installed — this skill needs the E2B code sandbox"
[ -n "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ] || die "no GH_TOKEN in the environment — this task is not bound to a repository"

# gh writes its config here; be explicit so a read-only HOME surprise is loud.
export GH_CONFIG_DIR="${GH_CONFIG_DIR:-${HOME:-$PWD}/.config/gh}"
mkdir -p "$GH_CONFIG_DIR"

gh auth setup-git >/dev/null 2>&1 || die "gh auth setup-git failed — the run's token is not usable for git"

NAME="${REPO##*/}"
# Relative to the sandbox's working directory, not $HOME — see note 3 above.
WORK_ROOT="${AF_WORK_ROOT:-$PWD/work}"
DEST="$WORK_ROOT/$NAME"
mkdir -p "$WORK_ROOT"

if [ -e "$DEST" ]; then
  # A second call in the same task should be idempotent, not destructive.
  [ -d "$DEST/.git" ] || die "$DEST exists and is not a git clone"
  echo "clone.sh: reusing the existing clone at $DEST" >&2
else
  git clone --depth 1 --single-branch "https://github.com/$REPO.git" "$DEST" \
    || die "clone failed — check the repository name, and that this task is bound to it"
fi

cd "$DEST"
DEST_ABS="$(pwd -P)"

# Identity for the commits this run makes. The bot is the actor the token
# belongs to, so attribute to it rather than to a person.
git config user.name "astralform-agent[bot]"
git config user.email "astralform-agent[bot]@users.noreply.github.com"

BASE="$(git rev-parse --abbrev-ref HEAD)"

# The remote is asked, not just the local refs: --single-branch fetched one
# branch, so a branch that already exists ON THE REMOTE is invisible to
# rev-parse. Branching over it here would only surface at `git push` as a
# non-fast-forward, at the very end of the run.
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  git fetch --depth 1 origin "$BRANCH":"$BRANCH" >/dev/null 2>&1 \
    || die "branch $BRANCH already exists on the remote and could not be fetched"
  git checkout "$BRANCH" >/dev/null 2>&1 || die "could not check out the existing branch $BRANCH"
  echo "clone.sh: $BRANCH already exists on the remote — continuing on it" >&2
elif git rev-parse --verify --quiet "$BRANCH" >/dev/null; then
  git checkout "$BRANCH" >/dev/null 2>&1 || die "branch $BRANCH exists but could not be checked out"
else
  git checkout -b "$BRANCH" >/dev/null 2>&1 || die "could not create branch $BRANCH"
fi

# ABSOLUTE, because each capsule.proc.exec is a fresh shell: nothing this
# script exports survives, so the caller must substitute this literal path into
# later commands rather than expect a $REPO_DIR variable to exist.
echo "REPO_DIR=$DEST_ABS"
echo "BRANCH=$BRANCH"
echo "BASE=$BASE"
