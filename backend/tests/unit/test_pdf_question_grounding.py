import json

from src.modules.pdf_questions.grounding import (
    build_grounded_passages,
    normalize_evidence_text,
    parse_grounded_response,
)
from src.modules.pdf_questions.schemas import PdfSourcePage


def _question(**changes):
    value = {
        "question": "What does the passage support?",
        "options": {"A": "Alpha", "B": "Beta", "C": "Gamma", "D": "Delta"},
        "correct_option": "A",
        "explanation": "The passage explicitly says Alpha.",
        "difficulty": 2,
        "expected_time_seconds": 30,
        "source_page": 3,
        "source_excerpt": "Alpha is the supported answer.",
        "confidence": 0.9,
    }
    value.update(changes)
    return value


def test_grounded_output_requires_a_real_excerpt_on_the_referenced_page() -> None:
    pages = {3: normalize_evidence_text("Alpha is the supported answer. More text.")}
    accepted = parse_grounded_response(
        json.dumps({"questions": [_question()]}),
        requested_count=2,
        page_texts=pages,
        maximum_response_characters=20_000,
    )
    rejected = parse_grounded_response(
        json.dumps({"questions": [_question(source_excerpt="Invented evidence")]}),
        requested_count=2,
        page_texts=pages,
        maximum_response_characters=20_000,
    )

    assert len(accepted.drafts) == 1
    assert accepted.rejected_count == 0
    assert rejected.drafts == ()
    assert rejected.rejected_count == 1


def test_grounded_output_removes_duplicate_drafts() -> None:
    result = parse_grounded_response(
        json.dumps({"questions": [_question(), _question(confidence=0.8)]}),
        requested_count=2,
        page_texts={3: "Alpha is the supported answer."},
        maximum_response_characters=20_000,
    )

    assert len(result.drafts) == 1
    assert result.rejected_count == 1


def test_passage_selection_covers_the_range_instead_of_only_early_pages() -> None:
    pages = [PdfSourcePage(page_number=index, text=f"Evidence from page {index}") for index in range(1, 21)]
    passages = build_grounded_passages(
        pages,
        maximum_characters=4_000,
        maximum_pages=5,
    )

    assert passages.page_numbers[0] == 1
    assert passages.page_numbers[-1] == 20
    assert len(passages.page_numbers) == 5
    assert len(set(passages.page_numbers)) == 5
