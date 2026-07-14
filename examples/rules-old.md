# Project rules

Ground rules for agents and humans working in this repository.
Read this file before making any change.

## Build commands

Run `make build` to compile and `make test` before every commit.
Never push with a red test suite.

## Code style

Four-space indentation, no tabs. Public functions need docstrings.
Keep modules under 400 lines; split by concern, not by layer.

## Testing

Every bug fix ships with a regression test. Prefer small, focused
unit tests over end-to-end scripts. Tests must run offline.

## Deploy checklist

Tag the release, run the smoke script, then promote the build.
Rollback instructions live in the runbook.

## Legacy notes

The old importer was removed in v2. Do not resurrect it; the
replacement lives in `importer2/`.
