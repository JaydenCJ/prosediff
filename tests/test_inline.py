"""Word-level inline diff: op runs, whitespace folding, and merging."""

from prosediff.inline import changed_ratio, inline_diff


def ops_as_tuples(old, new):
    return [(op.op, op.text) for op in inline_diff(old, new)]


def test_identical_text_is_one_equal_run():
    assert ops_as_tuples("keep it simple", "keep it simple") == [
        ("equal", "keep it simple")
    ]


def test_single_word_replace_is_delete_then_insert():
    ops = ops_as_tuples("run make test daily", "run make check daily")
    assert ops == [
        ("equal", "run make "),
        ("delete", "test"),
        ("insert", "check"),
        ("equal", " daily"),
    ]


def test_pure_insertion_keeps_surrounding_prose_equal():
    ops = ops_as_tuples("tag then promote", "tag then verify then promote")
    kinds = [op for op, _ in ops]
    assert kinds == ["equal", "insert", "equal"]
    assert ("insert", "verify then ") in ops


def test_whitespace_only_change_folds_and_merges_into_one_equal_run():
    # Re-spacing is not a reviewable prose change: the folded whitespace
    # must also merge with its neighbors into a single equal run.
    assert ops_as_tuples("one  two", "one two") == [("equal", "one two")]


def test_every_delete_is_immediately_followed_by_its_insert():
    ops = inline_diff("alpha beta gamma", "alpha delta epsilon")
    kinds = [op.op for op in ops]
    assert kinds.count("delete") == kinds.count("insert")
    for position, kind in enumerate(kinds):
        if kind == "delete":
            assert kinds[position + 1] == "insert"


def test_both_sides_reconstruct_from_word_ops():
    old = "never push a red build to main"
    new = "never push any red build to the main branch"
    ops = inline_diff(old, new)
    rebuilt_old = "".join(op.text for op in ops if op.op in ("equal", "delete"))
    rebuilt_new = "".join(op.text for op in ops if op.op in ("equal", "insert"))
    assert rebuilt_old == old
    assert rebuilt_new == new


def test_multiline_bodies_diff_across_lines():
    ops = ops_as_tuples("line one\nline two", "line one\nline three")
    assert ("delete", "two") in ops
    assert ("insert", "three") in ops


def test_changed_ratio_bounds():
    assert changed_ratio(inline_diff("same text", "same text")) == 0.0
    assert changed_ratio(inline_diff("", "")) == 0.0
    full = changed_ratio(inline_diff("aaa bbb", "xxx yyy"))
    assert 0.0 < full <= 1.0
    # Growing a body from nothing is a single pure insert.
    assert ops_as_tuples("", "brand new body") == [("insert", "brand new body")]
