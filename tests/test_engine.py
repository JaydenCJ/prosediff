"""End-to-end classification: parse two documents, get change verdicts.

These tests assert the *kind* each realistic edit produces — the contract
the CLI, the renderers, and every downstream consumer rely on.
"""

from prosediff import diff_text


def kinds(diff):
    return {c.section.title: c.kind for c in diff.changes}


def by_title(diff, title):
    for change in diff.changes:
        for side in (change.old, change.new):
            if side is not None and side.title == title:
                return change
    raise AssertionError(f"no change for {title!r}")


def test_identical_documents_have_no_changes():
    text = "# Top\n\nintro\n\n## Rules\n\nbe kind\n"
    diff = diff_text(text, text, old_name="before.md", new_name="after.md")
    assert not diff.has_changes
    assert all(c.kind == "unchanged" for c in diff.changes)
    assert (diff.old.name, diff.new.name) == ("before.md", "after.md")


def test_whitespace_only_reindent_is_unchanged():
    diff = diff_text("## A\n\n  rule one\n", "## A\n\nrule one\n")
    assert not diff.has_changes


def test_body_edit_in_place_is_edited():
    diff = diff_text("## A\n\nrun make test daily\n", "## A\n\nrun make check daily\n")
    change = by_title(diff, "A")
    assert change.kind == "edited"
    assert change.similarity is not None and change.similarity < 1.0
    assert change.similarity == round(change.similarity, 4)
    assert change.inline is not None


def test_pure_move_is_moved_with_full_similarity():
    old = "## A\n\nalpha body text\n\n## B\n\nbeta body text\n"
    new = "## B\n\nbeta body text\n\n## A\n\nalpha body text\n"
    diff = diff_text(old, new)
    moved = [c for c in diff.changes if c.kind == "moved"]
    assert len(moved) == 1  # LIS blames one section, not both
    assert moved[0].similarity == 1.0
    assert moved[0].inline is None


def test_rename_with_same_body_is_renamed():
    diff = diff_text("## Testing\n\nrun pytest\n", "## QA\n\nrun pytest\n")
    change = diff.changes[0]
    assert change.kind == "renamed"
    assert change.renamed and not change.moved


def test_rename_plus_body_edit_is_rewritten():
    old = "## Style\n\nindent with four spaces and no tabs anywhere\n"
    new = "## Code style\n\nindent with four spaces and never any tabs\n"
    diff = diff_text(old, new)
    change = diff.changes[0]
    assert change.kind == "rewritten"
    assert change.renamed


def test_move_plus_body_edit_is_rewritten():
    old = (
        "# Doc\n\n## Keep\n\nstable anchor text one\n"
        "\n## Drift\n\nthe deploy steps are tag then smoke then promote\n"
        "\n## Keep2\n\nstable anchor text two\n"
    )
    new = (
        "# Doc\n\n## Drift\n\nthe deploy steps are tag then verify then promote\n"
        "\n## Keep\n\nstable anchor text one\n"
        "\n## Keep2\n\nstable anchor text two\n"
    )
    diff = diff_text(old, new)
    change = by_title(diff, "Drift")
    assert change.kind == "rewritten"
    assert change.moved and not change.renamed
    assert change.matched_by == "path"


def test_reparenting_with_identical_body_is_moved():
    old = "# A\n\n## Rules\n\nnever push red builds\n\n# B\n\nbeta section body\n"
    new = "# A\n\nalpha now empty\n\n# B\n\nbeta section body\n\n## Rules\n\nnever push red builds\n"
    diff = diff_text(old, new)
    change = by_title(diff, "Rules")
    assert change.kind == "moved"
    assert change.old.parent_path == ("A",)
    assert change.new.parent_path == ("B",)


def test_added_and_removed_sections():
    diff = diff_text(
        "## Old only\n\nretired importer notes\n",
        "## New only\n\nsecurity checklist for releases\n",
    )
    assert kinds(diff) == {"Old only": "removed", "New only": "added"}


def test_report_lists_new_document_order_then_removals():
    old = "## Gone\n\nretired text\n\n## A\n\nalpha text here\n"
    new = "## Fresh\n\nbrand new text\n\n## A\n\nalpha text here\n"
    diff = diff_text(old, new)
    order = [(c.kind, c.section.title) for c in diff.changes]
    assert order == [
        ("added", "Fresh"),
        ("unchanged", "A"),
        ("removed", "Gone"),
    ]


def test_inline_diff_control_and_blank_edge_trimming():
    old = "## A\n\nfirst word old\n"
    new = "## A\n\nfirst word new\n"
    skipped = diff_text(old, new, with_inline=False)
    assert by_title(skipped, "A").inline is None
    # With inline on, the word diff starts at the prose, not the blank
    # spacer line under the heading.
    ops = by_title(diff_text(old, new), "A").inline
    assert ops[0].text.startswith("first")


def test_container_rename_cascades_to_moved_children():
    old = "## Ops\n\n### Deploy\n\nship the build\n"
    new = "## Operations\n\n### Deploy\n\nship the build\n"
    diff = diff_text(old, new)
    assert by_title(diff, "Ops").kind == "renamed"
    child = by_title(diff, "Deploy")
    assert child.kind == "moved"  # parent path changed, body identical
    assert child.old.parent_path == ("Ops",)


def test_counts_tally_every_kind():
    old = (
        "# Doc\n\nintro text\n\n## Move me\n\nmoved body text\n"
        "\n## Edit me\n\nplease run make test daily\n"
        "\n## Keep\n\nsteady anchor prose\n"
        "\n## Drop me\n\nold and busted content\n"
    )
    new = (
        "# Doc\n\nintro text\n\n## Edit me\n\nplease run make check daily\n"
        "\n## Keep\n\nsteady anchor prose\n"
        "\n## Move me\n\nmoved body text\n"
        "\n## Add me\n\nnew hotness content\n"
    )
    diff = diff_text(old, new)
    counts = diff.counts
    assert counts["added"] == 1
    assert counts["removed"] == 1
    assert counts["edited"] == 1
    assert counts["moved"] == 1
    assert counts["unchanged"] == 2  # '# Doc' and '## Keep'
    assert diff.has_changes
