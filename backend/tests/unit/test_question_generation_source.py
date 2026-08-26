import pytest

from src.modules.revisions.generation.source import (
    SourceContentUnavailableError,
    SourceBudgets,
    clean_html_text,
    prepare_question_source,
    truncate_text,
)


def _budgets(**overrides: int) -> SourceBudgets:
    values = {
        "maximum_source_characters": 200,
        "maximum_theory_characters": 80,
        "maximum_key_point_characters": 60,
        "maximum_notes_characters": 100,
    }
    values.update(overrides)
    return SourceBudgets(**values)


def test_clean_html_preserves_blocks_and_decodes_entities() -> None:
    assert clean_html_text("<p>A &amp; B</p><ul><li>One</li><li>Two</li></ul>") == (
        "A & B\nOne\nTwo"
    )


def test_clean_html_removes_script_and_style_contents() -> None:
    cleaned = clean_html_text(
        "<p>Visible</p><script>steal()</script><style>.secret{}</style><p>Safe</p>"
    )
    assert cleaned == "Visible\nSafe"
    assert "steal" not in cleaned
    assert "secret" not in cleaned


def test_urls_are_removed_from_every_source_section() -> None:
    source = prepare_question_source(
        title="Topic https://title.example/path",
        theory="Read https://theory.example and www.extra.example/page",
        key_points=["See docs.example.test/guide for more"],
        description_text="<p>https://unused.example</p>",
        budgets=_budgets(),
    )

    assert "http" not in source.content
    assert "www." not in source.content
    assert ".example" not in source.content


def test_generated_revision_source_is_preferred_over_raw_notes() -> None:
    source = prepare_question_source(
        title="Biology",
        theory="Cell theory",
        key_points=["Cells are units", "Cells divide"],
        description_text="<p>Raw notes must not be sent</p>",
        budgets=_budgets(),
    )

    assert source.source_kind == "GENERATED_REVISION"
    assert "Cell theory" in source.content
    assert "Cells are units" in source.content
    assert "Raw notes" not in source.content


def test_clean_notes_are_used_when_generated_content_is_absent() -> None:
    source = prepare_question_source(
        title="History",
        theory=None,
        key_points=[],
        description_text="<p>First&nbsp;fact</p><script>ignore me</script>",
        budgets=_budgets(),
    )

    assert source.source_kind == "CLEANED_NOTES"
    assert "First fact" in source.content
    assert "ignore me" not in source.content


def test_title_alone_is_not_treated_as_sufficient_study_content() -> None:
    with pytest.raises(SourceContentUnavailableError):
        prepare_question_source(
            title="Broad topic",
            theory=None,
            key_points=[],
            description_text="<script>nothing usable</script>",
            budgets=_budgets(),
        )


def test_source_character_budget_and_identifier_are_deterministic() -> None:
    arguments = {
        "title": "Topic",
        "theory": "x" * 100,
        "key_points": ["y" * 100],
        "description_text": None,
        "budgets": _budgets(maximum_source_characters=70),
    }
    first = prepare_question_source(**arguments)
    second = prepare_question_source(**arguments)

    assert len(first.content) == 70
    assert first == second
    assert len(first.source_identifier) == 64


def test_truncation_is_deterministic_and_never_exceeds_budget() -> None:
    assert truncate_text("12345   ", 5) == "12345"
    assert truncate_text("abcdef", 4) == "abcd"
