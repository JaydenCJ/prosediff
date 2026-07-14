"""Parser tests: heading detection, nesting, fences, and pseudo-sections.

The parser is the foundation of every diff verdict, so these tests pin the
tricky Markdown cases individually: code fences hiding ``#`` lines, setext
underlines vs thematic breaks, duplicate headings, and front matter.
"""

from prosediff import ParseError, parse_file, parse_text
from prosediff.model import FRONT_MATTER_TITLE, PREAMBLE_TITLE


def titles(text):
    return [s.title for s in parse_text(text).sections]


def test_flat_atx_headings_become_sections_in_order():
    doc = parse_text("# A\n\nbody a\n\n# B\n\nbody b\n")
    assert [s.title for s in doc.sections] == ["A", "B"]
    assert [s.level for s in doc.sections] == [1, 1]


def test_nested_headings_build_title_paths():
    doc = parse_text("# Top\n\n## Child\n\ntext\n\n### Grand\n\nmore\n")
    grand = doc.sections[-1]
    assert grand.path == ("Top", "Child", "Grand")
    assert doc.sections[1].children == [grand]


def test_level_jump_nests_under_nearest_shallower_heading():
    # '#' straight to '###' is common in hand-written rule files.
    doc = parse_text("# Top\n\n### Deep\n\ntext\n")
    assert doc.sections[1].path == ("Top", "Deep")


def test_body_belongs_to_own_section_not_children():
    doc = parse_text("## Parent\n\nparent text\n\n### Child\n\nchild text\n")
    parent = doc.sections[0]
    assert "parent text" in parent.body_text
    assert "child text" not in parent.body_text
    assert "child text" in parent.subtree_text


def test_preamble_before_first_heading_is_captured():
    doc = parse_text("intro line one\nintro line two\n\n# First\n\nbody\n")
    assert doc.sections[0].title == PREAMBLE_TITLE
    assert doc.sections[0].level == 0
    assert "intro line one" in doc.sections[0].body_text
    # ...but blank lines alone do not create a preamble section.
    blank = parse_text("\n\n# First\n\nbody\n")
    assert [s.title for s in blank.sections] == ["First"]


def test_front_matter_is_its_own_pseudo_section():
    text = "---\ntitle: rules\nversion: 2\n---\n\n# Top\n\nbody\n"
    doc = parse_text(text)
    assert doc.sections[0].title == FRONT_MATTER_TITLE
    assert "version: 2" in doc.sections[0].body_text
    assert doc.sections[1].title == "Top"
    # A lone '---' opener with no close is a thematic break, not metadata.
    broken = parse_text("---\ntitle: broken\n# Top\n\nbody\n")
    assert all(s.title != FRONT_MATTER_TITLE for s in broken.sections)


def test_hash_lines_inside_code_fences_are_not_headings():
    text = "# Real\n\n```bash\n# comment, not a heading\n## also code\n```\n"
    assert titles(text) == ["Real"]
    assert "# comment, not a heading" in parse_text(text).sections[0].body_text
    tilde = "# Real\n\n~~~\n# hidden\n~~~\n\n## After\n\ntext\n"
    assert titles(tilde) == ["Real", "After"]


def test_fence_closes_only_with_same_char_and_length():
    # A ``` fence is not closed by ~~~ nor by a shorter run of backticks.
    text = "# Real\n\n````\n~~~\n```\n# still code\n````\n\n## After\n\nx\n"
    assert titles(text) == ["Real", "After"]


def test_closing_hashes_are_stripped_from_atx_titles():
    doc = parse_text("## Setup ##\n\nbody\n")
    assert doc.sections[0].title == "Setup"


def test_hash_without_space_is_not_a_heading():
    # CommonMark: '#tag' is text, '# tag' is a heading.
    doc = parse_text("#hashtag\n\n# Real\n\nbody\n")
    assert [s.title for s in doc.sections] == [PREAMBLE_TITLE, "Real"]
    assert "#hashtag" in doc.sections[0].body_text


def test_setext_headings_recognized_but_not_after_list_items():
    doc = parse_text("Title\n=====\n\nintro\n\nSection\n-------\n\nbody\n")
    assert [(s.title, s.level) for s in doc.sections] == [
        ("Title", 1),
        ("Section", 2),
    ]
    # '---' after a bullet is a thematic break, not a setext underline.
    listed = parse_text("# Top\n\n- item\n---\n\ntext\n")
    assert [s.title for s in listed.sections] == ["Top"]


def test_duplicate_sibling_titles_get_disambiguated_paths():
    doc = parse_text("## Example\n\none\n\n## Example\n\ntwo\n")
    paths = [s.path for s in doc.sections]
    assert paths == [("Example",), ("Example [2]",)]


def test_line_spans_cover_heading_through_subtree():
    text = "# Top\n\nbody\n\n## Child\n\nchild body\n\n# Next\n\nend\n"
    doc = parse_text(text)
    top, child, nxt = doc.sections
    assert top.start_line == 1
    assert child.start_line == 5
    assert top.end_line == 8  # subtree ends right before '# Next'
    assert nxt.end_line == doc.line_count


def test_crlf_input_parses_and_bodies_are_clean():
    doc = parse_text("# Top\r\n\r\nbody line\r\n")
    assert doc.sections[0].title == "Top"
    assert doc.sections[0].body_text.strip() == "body line"


def test_empty_document_has_no_sections():
    doc = parse_text("")
    assert doc.sections == []
    assert doc.line_count == 0


def test_parse_file_missing_path_raises_parse_error(tmp_path):
    missing = tmp_path / "nope.md"
    try:
        parse_file(str(missing))
    except ParseError as exc:
        assert str(missing) in str(exc)
    else:  # pragma: no cover - the test must fail loudly if no error raised
        raise AssertionError("expected ParseError")


def test_parse_file_reads_utf8_from_disk(tmp_path):
    path = tmp_path / "rules.md"
    path.write_text("# 規約\n\n本文です。\n", encoding="utf-8")
    doc = parse_file(str(path))
    assert doc.sections[0].title == "規約"
    assert doc.name == str(path)
