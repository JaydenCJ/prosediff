# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-13

### Added

- Markdown section parser: ATX headings (with closing-hash form), setext
  headings, fenced code blocks (`` ``` `` and `~~~`, correct close matching),
  YAML front matter and preamble captured as pseudo-sections, duplicate
  sibling headings disambiguated, level jumps nested under the nearest
  shallower heading, line spans for every section.
- Three-pass section matcher: exact heading-path match, whitespace-insensitive
  content fingerprint match (moves and renames, with subtree fingerprints for
  prose-less container headings), and greedy token-similarity match for
  moved-and-rewritten sections with a configurable `--threshold`.
- Reorder blame via longest increasing subsequence, so moving one section
  flags one section.
- Change classification into seven kinds: `unchanged`, `edited`, `moved`,
  `renamed`, `rewritten`, `added`, `removed`.
- Word-level inline diff inside changed sections, with whitespace churn
  folded away and `{-old-}` / `{+new+}` markers.
- `prosediff diff` CLI with `text` (optionally colored), `markdown`
  (PR-comment shaped), and `json` (versioned schema, documented in
  `docs/diff-format.md`) output; GNU-diff exit codes (0 identical,
  1 differences, 2 error); `-` stdin operand for git piping.
- `prosediff outline` CLI printing one file's section tree with line spans,
  in text or JSON.
- Python API: `diff_text`, `diff_files`, `diff_documents`, `parse_text`,
  `parse_file`, `match_documents`, and the renderers.
- Runnable example pair (`examples/rules-old.md` / `rules-new.md`) covering
  every change kind, pinned by tests.
- 90 offline deterministic tests plus `scripts/smoke.sh` (prints `SMOKE OK`).

### Notes

- The repository ships no CI workflow; verification is local —
  `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/prosediff/releases/tag/v0.1.0
