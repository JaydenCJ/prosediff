# prosediff output format and matching rules

This document specifies the change kinds, the section-matching algorithm,
and the versioned JSON output schema (`"schema": 1`).

## Sections

A Markdown document is parsed into a tree of sections keyed by their
*heading path* — the tuple of ancestor titles down to the heading itself
(whitespace-normalized). The parser understands ATX headings (`#`–`######`,
including the `## Title ##` closing form), setext headings (`===`/`---`
underlines), and never treats a `#` inside a fenced code block as a heading.

Two pseudo-sections may appear at level 0:

| Pseudo-section | Contents |
|---|---|
| `(front matter)` | The YAML block between `---` fences at the very top |
| `(preamble)` | Any prose before the first real heading |

Duplicate sibling headings get disambiguated paths (`Example`, `Example [2]`)
so every section's path is unique within its document.

## Matching passes

Old and new sections are paired in three passes; each pass consumes its
matches so later passes only see leftovers.

| Pass | Pairs sections when | Detects |
|---|---|---|
| 1. path | full heading path is identical | edits in place |
| 2. fingerprint | prose is identical after whitespace normalization (`sha256`) | pure moves and renames |
| 3. similarity | token similarity of the prose ≥ threshold (default 0.5) | moved-and-rewritten sections |

Notes:

- Fingerprints are case-sensitive but whitespace-insensitive; empty bodies
  never match. A container heading with no prose of its own is fingerprinted
  by its *subtree*, so renaming a parent heading is one rename, not a
  delete-plus-add of every child.
- The similarity pass is greedy, best score first, with deterministic
  document-order tie-breaking. Similarity is `difflib` ratio over lowercased
  word tokens with autojunk disabled.
- Sections left unpaired become `added` / `removed`.

## Reorder blame

After matching, pairs are sorted by new-document position and a longest
increasing subsequence is computed over their old positions. Pairs outside
the LIS broke document order and are flagged as moved — so moving one
section up a ten-section file blames one section, not ten. A pair whose
parent path changed is flagged as moved regardless of order.

## Change kinds

| Kind | Meaning |
|---|---|
| `unchanged` | Same path, same prose, same relative order |
| `edited` | Same path and place, prose changed |
| `moved` | Prose identical; parent changed or document order broke |
| `renamed` | Prose identical; heading title changed |
| `rewritten` | Prose changed *and* the section was also moved or renamed |
| `added` | No counterpart in the old document |
| `removed` | No counterpart in the new document |

## JSON schema (version 1)

```json
{
  "schema": 1,
  "old": { "name": "rules-old.md", "sections": 6 },
  "new": { "name": "rules-new.md", "sections": 6 },
  "counts": { "added": 1, "removed": 1, "rewritten": 1, "edited": 1,
              "renamed": 1, "moved": 1, "unchanged": 1 },
  "changed": true,
  "changes": [
    {
      "kind": "moved",
      "old": { "title": "Deploy checklist", "path": ["Project rules", "Deploy checklist"],
               "level": 2, "line": 21, "position": 5 },
      "new": { "title": "Deploy checklist", "path": ["Project rules", "Deploy checklist"],
               "level": 2, "line": 6, "position": 2 },
      "similarity": 1.0,
      "moved": true,
      "renamed": false,
      "matched_by": "path"
    }
  ]
}
```

Field notes:

| Field | Type | Meaning |
|---|---|---|
| `schema` | int | Output format version; bumped on breaking changes |
| `changed` | bool | `true` iff any change kind other than `unchanged` exists |
| `changes[].old` / `.new` | object or null | `null` for `added` / `removed` respectively |
| `changes[].similarity` | float or null | Body similarity 0–1; `1.0` means identical prose |
| `changes[].moved` / `.renamed` | bool | Component flags; `rewritten` sets at least one |
| `changes[].matched_by` | string or null | `path`, `fingerprint`, or `similarity` |
| `changes[].inline` | array | Word-diff ops `{op, text}` with `op` ∈ equal/delete/insert; present only when the body changed |
| `*.line` | int | 1-based heading line in the source file |
| `*.position` | int | 1-based position among all sections of that document |

Changes are listed in new-document order; removed sections trail in
old-document order. `counts` always tallies every kind, even when
unchanged entries are omitted from `changes` (the default without `--all`).

Compatibility promise: within schema version 1, fields are only added,
never renamed or removed. Anything that changes the meaning of an existing
field bumps `schema`.
