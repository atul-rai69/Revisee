import random

from src.modules.revisions.selection import (
    QuestionCandidate,
    select_label_questions,
    select_random_question_ids,
)


def candidate(question_id: int, *label_ids: int) -> QuestionCandidate:
    return QuestionCandidate(question_id, frozenset(label_ids))


def test_random_selection_is_seeded_unique_and_without_replacement() -> None:
    candidates = [candidate(index) for index in range(1, 8)]

    first, first_shortage = select_random_question_ids(
        candidates, 5, random.Random(12)
    )
    second, second_shortage = select_random_question_ids(
        candidates, 5, random.Random(12)
    )

    assert first == second
    assert len(first) == len(set(first)) == 5
    assert first_shortage == second_shortage == 0


def test_random_shortage_returns_no_partial_selection() -> None:
    selected, shortage = select_random_question_ids(
        [candidate(1), candidate(1), candidate(2)],
        3,
        random.Random(1),
    )
    assert selected == []
    assert shortage == 1


def test_label_matching_protects_scarce_label_from_overlap() -> None:
    candidates = [
        candidate(1, 1, 2),
        candidate(2, 1, 2),
        candidate(3, 1),
        candidate(4, 1),
    ]

    result = select_label_questions(candidates, [1, 2], 2, random.Random(3))

    assert result.complete
    assert len({entry.question_id for entry in result.ordered_questions}) == 4
    assert [entry.label_id for entry in result.ordered_questions] == [1, 2, 1, 2]
    assert {entry.question_id for entry in result.ordered_questions if entry.label_id == 2} == {
        1,
        2,
    }


def test_label_matching_is_deterministic_for_same_seed() -> None:
    candidates = [
        candidate(1, 1, 2),
        candidate(2, 1, 2),
        candidate(3, 1),
        candidate(4, 2),
        candidate(5, 1),
        candidate(6, 2),
    ]

    first = select_label_questions(candidates, [1, 2], 2, random.Random(9))
    second = select_label_questions(candidates, [1, 2], 2, random.Random(9))

    assert first == second


def test_label_shortage_reports_maximum_assignable_unique_questions() -> None:
    candidates = [
        candidate(1, 1, 2),
        candidate(2, 1),
        candidate(3, 1),
    ]

    result = select_label_questions(candidates, [1, 2], 2, random.Random(2))
    shortages = {shortage.label_id: shortage for shortage in result.shortages}

    assert not result.complete
    assert len(result.ordered_questions) == 3
    assert shortages[1].assigned == 2
    assert shortages[1].shortage == 0
    assert shortages[2].eligible_unique == 1
    assert shortages[2].assigned == 1
    assert shortages[2].shortage == 1


def test_duplicate_candidate_rows_merge_label_eligibility() -> None:
    result = select_label_questions(
        [candidate(1, 1), candidate(1, 2), candidate(2, 1), candidate(3, 2)],
        [1, 2],
        1,
        random.Random(4),
    )
    assert result.complete
    assert len({entry.question_id for entry in result.ordered_questions}) == 2
