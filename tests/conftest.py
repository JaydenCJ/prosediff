"""Shared test setup.

Makes ``prosediff`` importable straight from a clean checkout, so the suite
runs with plain ``pytest`` before any ``pip install -e .`` — the same
zero-setup path scripts/smoke.sh uses.
"""

import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
