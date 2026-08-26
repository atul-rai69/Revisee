from src.modules.revisions.generation.fingerprint import (
    deduplicate_questions,
    question_fingerprint,
)
from src.modules.revisions.generation.schemas import ValidatedGeneratedQuestion


def _question(text: str, options: list[str]) -> ValidatedGeneratedQuestion:
    return ValidatedGeneratedQuestion.model_validate(
        {
            "question": text,
            "options": options,
            "correct_answer": "0",
            "difficulty_level": 1,
            "expected_time_seconds": 10,
            "explanation": "Explanation",
        },
        context={"maximum_expected_time_seconds": 60},
    )


def test_fingerprint_normalizes_unicode_case_and_whitespace() -> None:
    first = question_fingerprint("  WHAT  is Ａ? ", ["One", "Two", "Three", "Four"])
    second = question_fingerprint("what is a?", ["one", "two", "three", "four"])
    assert first == second


def test_fingerprint_is_stable_when_option_order_changes() -> None:
    options = ["One", "Two", "Three", "Four"]
    assert question_fingerprint("Question?", options) == question_fingerprint(
        "Question?", list(reversed(options))
    )


def test_punctuation_is_preserved() -> None:
    options = ["One", "Two", "Three", "Four"]
    assert question_fingerprint("Question?", options) != question_fingerprint(
        "Question!", options
    )


def test_in_batch_and_cross_call_duplicates_are_removed() -> None:
    first = _question("Question?", ["One", "Two", "Three", "Four"])
    same = _question(" question? ", ["Four", "Three", "Two", "One"])
    other = _question("Other?", ["A", "B", "C", "D"])

    initial = deduplicate_questions([first, same, other])
    repeated_call = deduplicate_questions([first, other], initial.fingerprints)

    assert len(initial.questions) == 2
    assert initial.duplicate_count == 1
    assert repeated_call.questions == ()
    assert repeated_call.duplicate_count == 2
