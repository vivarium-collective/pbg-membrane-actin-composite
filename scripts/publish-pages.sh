#!/usr/bin/env bash
# Publish the STATIC investigation report to the gh-pages branch.
#
# Opt-in, non-default: the normal report flow (`/pbg-report`) is untouched and
# still produces the interactive (server-backed) SPA at reports/index.html. This
# script builds the self-contained static report (scripts/build-static-report.py)
# and pushes it to gh-pages root so the README's GitHub Pages link serves it. The
# original demo is preserved at /demo/.
#
# Usage:
#   scripts/publish-pages.sh [--slug <investigation>] [--build-only] [--no-push]
#
#   --build-only   build _site/ and stop (no gh-pages worktree/commit/push)
#   --no-push      build + stage into the gh-pages worktree + commit, but don't push
#   --slug         investigation slug (default: membrane-actin-ratchet)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -f workspace.yaml ] || { echo "ERROR: not a workspace (no workspace.yaml) at $ROOT" >&2; exit 1; }

SLUG="membrane-actin-ratchet"
BUILD_ONLY=0
NO_PUSH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --slug) SLUG="$2"; shift 2;;
    --build-only) BUILD_ONLY=1; shift;;
    --no-push) NO_PUSH=1; shift;;
    -h|--help) sed -n '2,16p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="python3"
TODAY="$(date +%F)"
OUT="$ROOT/_site"

echo "==> building static report (slug=$SLUG, date=$TODAY)"
"$PY" "$ROOT/scripts/build-static-report.py" --out "$OUT" --slug "$SLUG" --date "$TODAY"
[ -f "$OUT/index.html" ] || { echo "ERROR: build produced no _site/index.html" >&2; exit 1; }

if [ "$BUILD_ONLY" -eq 1 ]; then
  echo "==> --build-only: wrote $OUT/index.html (+ figures/). Not publishing."
  exit 0
fi

WT="$ROOT/.pbg/worktrees/gh-pages"
echo "==> publishing to gh-pages via worktree $WT"
git fetch origin gh-pages --quiet
git worktree remove --force "$WT" 2>/dev/null || true
rm -rf "$WT"
git worktree add "$WT" gh-pages >/dev/null

# Replace the root report + figures; leave demo/ and everything else intact.
cp "$OUT/index.html" "$WT/index.html"
rm -rf "$WT/figures"
cp -R "$OUT/figures" "$WT/figures"

git -C "$WT" add -A
if git -C "$WT" diff --cached --quiet; then
  echo "==> no changes to publish (gh-pages already up to date)"
else
  git -C "$WT" commit -q -m "publish: static investigation report ($SLUG) — $TODAY"
  if [ "$NO_PUSH" -eq 1 ]; then
    echo "==> --no-push: committed to gh-pages worktree, not pushed"
  else
    git -C "$WT" push origin gh-pages
    echo "==> published. Pages rebuilds in ~1-2 min:"
    echo "    https://vivarium-collective.github.io/${PWD##*/}/"
  fi
fi

git worktree remove --force "$WT" 2>/dev/null || true
echo "==> done"
