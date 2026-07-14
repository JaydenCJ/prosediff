#!/usr/bin/env bash
# Smoke test for prosediff: run the real CLI end-to-end against the shipped
# example pair and assert on move/rename/rewrite detection, output formats,
# exit codes, and stdin mode. Self-contained: pure stdlib, no network,
# idempotent (works from a clean tree, no install required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# Zero runtime dependencies, so running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/prosediff-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

OLD="$ROOT/examples/rules-old.md"
NEW="$ROOT/examples/rules-new.md"

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

# 1. Identical inputs exit 0 and report no changes.
same_out="$("$PYTHON" -m prosediff diff "$OLD" "$OLD")" \
  || fail "diff of identical files should exit 0"
echo "$same_out" | grep -q "no changes" || fail "identical diff missing 'no changes'"

# 2. The example pair exits 1 and detects a move, a rename, and a rewrite.
set +e
diff_out="$("$PYTHON" -m prosediff diff "$OLD" "$NEW" --color never)"
diff_rc=$?
set -e
echo "$diff_out" | sed 's/^/[diff] /'
[ "$diff_rc" -eq 1 ] || fail "diff with changes should exit 1, got $diff_rc"
echo "$diff_out" | grep -q "> moved     ## Deploy checklist" \
  || fail "move of 'Deploy checklist' not detected"
echo "$diff_out" | grep -q "\^ renamed   ## Testing -> ## QA rules" \
  || fail "rename of 'Testing' not detected"
echo "$diff_out" | grep -q "! rewritten ## Code style -> ## Style guide" \
  || fail "rewrite of 'Code style' not detected"
echo "$diff_out" | grep -q "{-test\`-}{+check\`+}" \
  || fail "word-level inline diff missing"

# 3. JSON report parses, is versioned, and carries the verdicts.
set +e
"$PYTHON" -m prosediff diff "$OLD" "$NEW" --format json > "$WORKDIR/report.json"
json_rc=$?
set -e
[ "$json_rc" -eq 1 ] || fail "json diff should exit 1, got $json_rc"
"$PYTHON" - "$WORKDIR/report.json" <<'PY' || fail "json report failed validation"
import json, sys
payload = json.load(open(sys.argv[1]))
assert payload["schema"] == 1, "schema version"
assert payload["changed"] is True, "changed flag"
kinds = {c["kind"] for c in payload["changes"]}
assert {"moved", "renamed", "rewritten", "edited", "added", "removed"} <= kinds, kinds
PY
echo "[json] schema 1 report validated"

# 4. Markdown format renders a PR-comment-shaped report.
"$PYTHON" -m prosediff diff "$OLD" "$NEW" --format markdown > "$WORKDIR/report.md" || true
grep -q '^### prosediff:' "$WORKDIR/report.md" || fail "markdown header missing"
grep -q -- '- \*\*moved\*\*' "$WORKDIR/report.md" || fail "markdown moved bullet missing"

# 5. Outline shows the section tree with line spans.
outline_out="$("$PYTHON" -m prosediff outline "$NEW")"
echo "$outline_out" | sed 's/^/[outline] /'
echo "$outline_out" | grep -q "6 sections" || fail "outline section count wrong"
echo "$outline_out" | grep -Eq '## Deploy checklist  \[lines [0-9]+-[0-9]+\]' \
  || fail "outline missing line spans"

# 6. Stdin mode: pipe the old side in, like `git show HEAD:file | prosediff diff - file`.
set +e
stdin_out="$("$PYTHON" -m prosediff diff - "$NEW" < "$OLD")"
stdin_rc=$?
set -e
[ "$stdin_rc" -eq 1 ] || fail "stdin diff should exit 1, got $stdin_rc"
echo "$stdin_out" | grep -q "<stdin> -> " || fail "stdin input not labelled"

# 7. Bad usage exits 2 (distinct from 'differences found').
set +e
"$PYTHON" -m prosediff diff "$OLD" "$NEW" --threshold 2 >/dev/null 2>"$WORKDIR/err.txt"
bad_rc=$?
set -e
[ "$bad_rc" -eq 2 ] || fail "invalid threshold should exit 2, got $bad_rc"
grep -q "threshold" "$WORKDIR/err.txt" || fail "threshold error message missing"

# 8. --version agrees with the package.
version_out="$("$PYTHON" -m prosediff --version)"
pkg_version="$("$PYTHON" -c 'import prosediff; print(prosediff.__version__)')"
[ "$version_out" = "prosediff $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"

echo "SMOKE OK"
