"""Normalization and similarity primitives.

Fingerprint semantics are load-bearing: two bodies fingerprinting equal is
what turns a delete-plus-add into a detected move, so the exact rules
(whitespace-insensitive, case-sensitive, empty-is-never-equal) get their
own tests.
"""

from prosediff.textnorm import (
    fingerprint,
    normalize_block,
    similarity,
    title_key,
    tokens,
)


def test_normalize_collapses_space_runs_and_trailing_whitespace():
    assert normalize_block("a  b\t c  \n d") == "a b c\nd"


def test_normalize_drops_blank_edge_lines_but_keeps_inner_breaks():
    assert normalize_block("\n\nfirst\n\nsecond\n\n") == "first\n\nsecond"


def test_normalize_preserves_reflow_as_a_real_change():
    # Joining two lines into one is an edit, not whitespace noise.
    assert normalize_block("one\ntwo") != normalize_block("one two")


def test_fingerprint_ignores_indentation_but_not_case():
    assert fingerprint("  rule one\n  rule two") == fingerprint("rule one\nrule two")
    assert fingerprint("Always run tests") != fingerprint("always run tests")


def test_fingerprint_of_whitespace_only_text_is_empty_sentinel():
    # Empty bodies must never fingerprint-match each other.
    assert fingerprint("   \n\t\n") == ""
    assert fingerprint("") == ""


def test_tokens_lowercase_and_split_punctuation():
    assert tokens("Run `make test`!") == ["run", "`", "make", "test", "`", "!"]


def test_similarity_bounds_identical_disjoint_and_empty():
    assert similarity(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert similarity(["a", "b"], ["x", "y"]) == 0.0
    assert similarity([], []) == 1.0
    assert similarity([], ["a"]) == 0.0
    assert similarity(["a"], []) == 0.0


def test_similarity_is_symmetric_for_partial_overlap():
    a = tokens("keep modules under 400 lines split by concern")
    b = tokens("keep modules under 500 lines split by layer")
    assert similarity(a, b) == similarity(b, a)
    assert 0.5 < similarity(a, b) < 1.0


def test_title_key_collapses_internal_whitespace():
    assert title_key("  Build   commands ") == "Build commands"
