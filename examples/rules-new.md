# Project rules

Ground rules for agents and humans working in this repository.
Read this file before making any change.

## Deploy checklist

Tag the release, run the smoke script, then promote the build.
Rollback instructions live in the runbook.

## Build commands

Run `make build` to compile and `make check` before every commit.
Never push with a red test suite.

## QA rules

Every bug fix ships with a regression test. Prefer small, focused
unit tests over end-to-end scripts. Tests must run offline.

## Style guide

Four-space indentation, no tabs. Public functions need docstrings
and type hints. Keep modules under 400 lines; split by concern.

## Security

Never commit secrets. Credentials come from the environment, and
example configs use `127.0.0.1` or `example.test` hosts only.
