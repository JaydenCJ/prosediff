# Contributing to prosediff

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Development setup

```bash
git clone https://github.com/JaydenCJ/prosediff
cd prosediff
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the checks

```bash
pytest                 # 90 unit and CLI tests, fully offline
bash scripts/smoke.sh  # end-to-end: real CLI runs against examples/
```

Both must pass before a pull request is reviewed; the smoke script prints
`SMOKE OK` on success. The suite needs no network, no install (a clean
checkout works), and finishes in seconds.

## Ground rules

- **No new runtime dependencies.** The package is standard-library only;
  that is a feature. Test-only dependencies belong in the `dev` extra.
- **Verdict changes need tests and docs.** Anything that changes what kind a
  scenario classifies to, or the JSON output, must update
  `docs/diff-format.md` (and bump `schema` for breaking JSON changes) in the
  same pull request.
- **Keep logic in pure modules.** Parsing, matching, classification, and
  rendering are side-effect-free; the CLI stays a thin argparse shell.
  New behavior goes into a pure function with a unit test first.
- **Every public API needs an English docstring and a test.** The example
  pair in `examples/` is quoted by the README and pinned by
  `tests/test_examples.py`; keep code, docs, and examples in sync.
- **Keep the three READMEs aligned.** `README.md`, `README.zh.md`, and
  `README.ja.md` are line-for-line parallel; update all three when you
  change one (English is the authoritative version).

## Reporting bugs

Please include the two Markdown inputs (or a minimized pair), the exact
command line, the output of `prosediff --version`, and what verdict you
expected. A failing `pytest` test case is the fastest path to a fix.

## Security

Please do not report security issues in public issues; use GitHub's private
vulnerability reporting on the repository instead.
