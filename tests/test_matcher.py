"""Matching passes: path, fingerprint, similarity, and reorder blame.

Each test builds the smallest pair of documents that exercises one pairing
rule, so a regression pinpoints the exact pass that broke.
"""

from prosediff.matcher import match_documents, mark_reordered
from prosediff.parser import parse_text


def match(old_text, new_text, threshold=0.5):
    return match_documents(
        parse_text(old_text, "old"), parse_text(new_text, "new"), threshold
    )


def pair_map(result):
    return {pair.old.title: pair for pair in result.pairs}


def test_same_path_sections_match_even_when_body_changed():
    result = match("## A\n\nold body\n", "## A\n\ncompletely new words\n")
    assert pair_map(result)["A"].matched_by == "path"
    assert result.added == [] and result.removed == []


def test_path_match_requires_full_ancestry_not_just_title():
    # 'Setup' under two different parents is two different sections.
    old = "# One\n\n## Setup\n\nsteps\n"
    new = "# Two\n\n## Setup\n\nsteps\n"
    result = match(old, new)
    setup = pair_map(result)["Setup"]
    assert setup.matched_by == "fingerprint"  # not the path pass


def test_pure_move_is_matched_by_fingerprint():
    old = "## A\n\nalpha text\n\n## B\n\nshared rules live here\n"
    new = "## B\n\nshared rules live here\n\n## A\n\nalpha text\n"
    result = match(old, new)
    assert {p.old.title for p in result.pairs} == {"A", "B"}
    assert all(p.similarity == 1.0 for p in result.pairs)


def test_rename_with_identical_body_is_matched_by_fingerprint():
    result = match("## Testing\n\nrun pytest often\n", "## QA\n\nrun pytest often\n")
    pair = result.pairs[0]
    assert pair.matched_by == "fingerprint"
    assert (pair.old.title, pair.new.title) == ("Testing", "QA")


def test_fingerprint_prefers_same_title_candidate_over_rename():
    # Old 'Rules' must pair with new 'Rules', not the same-body 'Copy'.
    old = "# Top\n\n## Rules\n\nidentical body text\n"
    new = (
        "# Other\n\n## Copy\n\nidentical body text\n"
        "\n## Rules\n\nidentical body text\n"
    )
    result = match(old, new)
    rules = pair_map(result)["Rules"]
    assert rules.new.title == "Rules"


def test_container_heading_matched_by_subtree_fingerprint():
    # 'Ops' has no prose of its own; its identity is its children.
    old = "## Ops\n\n### Deploy\n\nship it\n\n### Rollback\n\nundo it\n"
    new = "## Operations\n\n### Deploy\n\nship it\n\n### Rollback\n\nundo it\n"
    result = match(old, new)
    container = pair_map(result)["Ops"]
    assert container.new.title == "Operations"
    assert container.matched_by == "fingerprint"


def test_empty_sections_never_match_by_content():
    # Two bare headings with no body share nothing identifiable.
    result = match("## Alpha\n", "## Beta\n")
    assert result.pairs == []
    assert [s.title for s in result.removed] == ["Alpha"]
    assert [s.title for s in result.added] == ["Beta"]


def test_rewritten_and_renamed_section_matched_by_similarity():
    old = "## Style\n\nfour space indent, no tabs, docstrings required\n"
    new = "## Code style\n\nfour space indent, no tabs, type hints required\n"
    result = match(old, new)
    pair = result.pairs[0]
    assert pair.matched_by == "similarity"
    assert 0.5 <= pair.similarity < 1.0


def test_similarity_below_threshold_yields_add_and_remove():
    old = "## Notes\n\nthe quick brown fox jumps over the lazy dog\n"
    new = "## Notes2\n\ncompletely unrelated prose about invoices\n"
    result = match(old, new)
    assert result.pairs == []
    assert len(result.removed) == 1 and len(result.added) == 1


def test_threshold_parameter_tightens_the_similarity_pass():
    old = "## A\n\nkeep modules under 400 lines split by concern\n"
    new = "## B\n\nkeep modules under 500 lines split by layer\n"
    loose = match(old, new, threshold=0.5)
    strict = match(old, new, threshold=0.95)
    assert len(loose.pairs) == 1
    assert strict.pairs == []


def test_similarity_ties_break_toward_document_order():
    # Both new sections score identically against old 'A'; the earlier
    # old/new positions must win so results are stable run to run.
    old = "## A\n\nshared words here\n\n## B\n\nshared words here\n"
    new = "## C\n\nshared words here!\n\n## D\n\nshared words here!\n"
    result = match(old, new)
    titles = {(p.old.title, p.new.title) for p in result.pairs}
    assert titles == {("A", "C"), ("B", "D")}


def test_mark_reordered_blames_the_minimal_moved_set():
    # Move one section to the front of five: exactly one pair is blamed.
    old = "\n".join(f"## S{i}\n\nbody {i} text\n" for i in range(5))
    new_order = [4, 0, 1, 2, 3]
    new = "\n".join(f"## S{i}\n\nbody {i} text\n" for i in new_order)
    result = match(old, new)
    flags = mark_reordered(result.pairs)
    moved = [p.old.title for p, f in zip(result.pairs, flags) if f]
    assert moved == ["S4"]


def test_mark_reordered_stays_quiet_when_order_is_preserved():
    result = match("## A\n\none\n\n## B\n\ntwo\n", "## A\n\none\n\n## B\n\ntwo\n")
    assert mark_reordered(result.pairs) == [False, False]
    assert mark_reordered([]) == []
