# prosediff examples

`rules-old.md` and `rules-new.md` are two versions of a small CLAUDE.md-style
rule file. Between them, one edit session did everything a rule review
usually has to untangle:

| Section | What happened | prosediff verdict |
|---|---|---|
| `## Deploy checklist` | Moved from position 5 to position 2, prose untouched | `moved` |
| `## Build commands` | One command changed (`make test` → `make check`) | `edited` |
| `## Testing` | Renamed to `## QA rules`, prose untouched | `renamed` |
| `## Code style` | Renamed to `## Style guide` *and* the prose was revised | `rewritten` |
| `## Security` | New section | `added` |
| `## Legacy notes` | Deleted | `removed` |

Run the section-aware diff (exit code is 1 because differences exist):

```bash
prosediff diff examples/rules-old.md examples/rules-new.md
```

Compare with `diff -u examples/rules-old.md examples/rules-new.md`, which
shows the moved and renamed sections as ~20 deleted and ~20 added lines.

Other things to try from the repository root:

```bash
# The section tree of one file, with line spans
prosediff outline examples/rules-new.md

# Machine-readable report for scripting (schema documented in docs/diff-format.md)
prosediff diff examples/rules-old.md examples/rules-new.md --format json

# A report shaped for pasting into a PR comment
prosediff diff examples/rules-old.md examples/rules-new.md --format markdown

# Review your working-tree CLAUDE.md against HEAD without a difftool setup
git show HEAD:CLAUDE.md | prosediff diff - CLAUDE.md
```

These files are also exercised by `tests/test_examples.py` and
`scripts/smoke.sh`, so the verdicts in this table are pinned by tests.
