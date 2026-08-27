import random
from datetime import datetime, timedelta
from decimal import Decimal

from src.modules.revisions.smart_selection import (
    SmartQuestionCandidate,
    candidate_tier,
    select_smart_question_ids,
)
from src.modules.revisions.selection import QuestionCandidate, select_random_question_ids


AS_OF = datetime(2026, 8, 27, 12, 0, 0)


class RecordingRandomizer:
    def __init__(self) -> None:
        self.shuffle_lengths: list[int] = []

    def sample(self, population, k: int):
        return list(population[:k])

    def shuffle(self, values: list[int]) -> None:
        self.shuffle_lengths.append(len(values))
        values.reverse()


def candidate(
    question_id: int,
    item_id: int,
    *,
    score: str | None = None,
    attempts: int = 0,
    review_delta_days: int | None = None,
) -> SmartQuestionCandidate:
    return SmartQuestionCandidate(
        question_id=question_id,
        learning_item_id=item_id,
        mastery_score=Decimal(score) if score is not None else None,
        total_attempts=attempts,
        next_review_at=(
            AS_OF + timedelta(days=review_delta_days)
            if review_delta_days is not None
            else None
        ),
    )


def test_candidate_tiers_respect_evidence_and_boundaries() -> None:
    assert candidate_tier(candidate(1, 1, score="20", attempts=2), AS_OF) == 3
    assert candidate_tier(candidate(2, 2, score="59.99", attempts=3), AS_OF) == 1
    assert candidate_tier(
        candidate(3, 3, score="60.00", attempts=3, review_delta_days=0),
        AS_OF,
    ) == 2
    assert candidate_tier(
        candidate(4, 4, score="60.00", attempts=3, review_delta_days=1),
        AS_OF,
    ) == 3


def test_smart_prioritizes_weak_then_due_and_fills_exact_count() -> None:
    candidates = [
        candidate(1, 1, score="30", attempts=3),
        candidate(2, 2, score="70", attempts=3, review_delta_days=-1),
        candidate(3, 3),
        candidate(4, 3),
    ]
    result = select_smart_question_ids(candidates, 3, AS_OF, random.Random(4))

    assert result.strategy_used == "SMART"
    assert len(result.question_ids) == 3
    assert {1, 2} <= set(result.question_ids)


def test_round_robin_and_soft_cap_prevent_large_item_domination() -> None:
    candidates = [
        *[candidate(index, 1, score="20", attempts=5) for index in range(1, 9)],
        candidate(20, 2, score="30", attempts=4),
        candidate(30, 3),
        candidate(31, 3),
        candidate(32, 3),
    ]
    result = select_smart_question_ids(candidates, 6, AS_OF, random.Random(2))
    item_by_question = {entry.question_id: entry.learning_item_id for entry in candidates}
    counts = {
        item_id: sum(item_by_question[value] == item_id for value in result.question_ids)
        for item_id in (1, 2, 3)
    }

    assert counts[1] <= 3
    assert counts[2] >= 1
    assert counts[3] >= 1


def test_soft_cap_relaxes_only_when_alternatives_are_exhausted() -> None:
    candidates = [
        *[candidate(index, 1, score="20", attempts=5) for index in range(1, 8)],
        candidate(20, 2),
    ]
    result = select_smart_question_ids(candidates, 6, AS_OF, random.Random(3))
    assert len(result.question_ids) == 6
    assert 20 in result.question_ids


def test_deduplication_and_total_bank_shortage() -> None:
    repeated = candidate(1, 1, score="20", attempts=3)
    result = select_smart_question_ids(
        [repeated, repeated, candidate(2, 2)],
        3,
        AS_OF,
        random.Random(1),
    )
    assert result.question_ids == ()
    assert result.assignable_question_count == 2
    assert result.shortage == 1


def test_no_actionable_evidence_uses_seeded_random_fallback() -> None:
    candidates = [candidate(index, index) for index in range(1, 7)]
    first = select_smart_question_ids(candidates, 3, AS_OF, random.Random(9))
    second = select_smart_question_ids(candidates, 3, AS_OF, random.Random(9))

    assert first == second
    assert first.strategy_used == "RANDOM"
    assert len(set(first.question_ids)) == 3
    random_ids, shortage = select_random_question_ids(
        [QuestionCandidate(entry.question_id) for entry in candidates],
        3,
        random.Random(9),
    )
    assert shortage == 0
    assert first.question_ids == tuple(random_ids)


def test_partial_personalization_remains_smart_and_final_order_is_shuffled() -> None:
    candidates = [
        candidate(1, 1, score="20", attempts=3),
        candidate(2, 2),
        candidate(3, 3),
        candidate(4, 4),
    ]
    first = select_smart_question_ids(candidates, 4, AS_OF, random.Random(11))
    second = select_smart_question_ids(candidates, 4, AS_OF, random.Random(11))
    assert first == second
    assert first.strategy_used == "SMART"
    assert set(first.question_ids) == {1, 2, 3, 4}

    recording = RecordingRandomizer()
    recorded = select_smart_question_ids(candidates, 4, AS_OF, recording)
    assert len(recorded.question_ids) == 4
    assert recording.shuffle_lengths[-1] == 4
