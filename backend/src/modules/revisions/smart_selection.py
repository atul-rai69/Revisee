from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Sequence

from src.modules.mastery.weak_areas import (
    MINIMUM_ATTEMPTS,
    WEAK_MASTERY_BELOW,
    weak_area_order_key,
)
from src.modules.revisions.selection import (
    QuestionCandidate,
    Randomizer,
    select_random_question_ids,
)


@dataclass(frozen=True, slots=True)
class SmartQuestionCandidate:
    question_id: int
    learning_item_id: int
    mastery_score: Decimal | None
    total_attempts: int
    next_review_at: datetime | None


@dataclass(frozen=True, slots=True)
class SmartSelectionResult:
    question_ids: tuple[int, ...]
    strategy_used: Literal["RANDOM", "SMART"]
    requested_question_count: int
    assignable_question_count: int

    @property
    def shortage(self) -> int:
        return max(0, self.requested_question_count - self.assignable_question_count)


def candidate_tier(candidate: SmartQuestionCandidate, as_of: datetime) -> int:
    if (
        candidate.mastery_score is not None
        and candidate.total_attempts >= MINIMUM_ATTEMPTS
    ):
        score = Decimal(candidate.mastery_score)
        if score < WEAK_MASTERY_BELOW:
            return 1
        if candidate.next_review_at is not None and candidate.next_review_at <= as_of:
            return 2
    return 3


def select_smart_question_ids(
    candidates: Sequence[SmartQuestionCandidate],
    question_count: int,
    as_of: datetime,
    randomizer: Randomizer | None = None,
) -> SmartSelectionResult:
    rng = randomizer or random.Random()
    unique = _deduplicate(candidates)
    if len(unique) < question_count:
        return SmartSelectionResult((), "SMART", question_count, len(unique))

    groups: dict[int, list[int]] = {}
    evidence_by_item: dict[int, SmartQuestionCandidate] = {}
    for candidate in unique:
        groups.setdefault(candidate.learning_item_id, []).append(candidate.question_id)
        evidence_by_item.setdefault(candidate.learning_item_id, candidate)
    tiers = {
        tier: [
            item_id
            for item_id, evidence in evidence_by_item.items()
            if candidate_tier(evidence, as_of) == tier
        ]
        for tier in (1, 2, 3)
    }
    tiers[1].sort(
        key=lambda item_id: _item_order(
            evidence_by_item[item_id], "DEMONSTRATED_WEAKNESS", as_of
        )
    )
    tiers[2].sort(
        key=lambda item_id: _item_order(
            evidence_by_item[item_id], "DUE_REVIEW", as_of
        )
    )
    tiers[3].sort()

    actionable = bool(tiers[1] or tiers[2])
    if not actionable:
        ids, shortage = select_random_question_ids(
            [QuestionCandidate(candidate.question_id) for candidate in unique],
            question_count,
            rng,
        )
        if shortage:
            raise AssertionError("SMART bank size changed during RANDOM fallback")
        return SmartSelectionResult(
            tuple(ids), "RANDOM", question_count, len(unique)
        )

    for bucket in groups.values():
        rng.shuffle(bucket)

    soft_cap = max(1, math.ceil(question_count / 2))
    selected: list[int] = []
    selected_by_item = {item_id: 0 for item_id in groups}

    for tier in (1, 2):
        _round_robin(
            tiers[tier],
            groups,
            selected_by_item,
            selected,
            question_count,
            soft_cap,
        )

    ranked_items = tiers[1] + tiers[2] + tiers[3]
    while len(selected) < question_count:
        available = [item_id for item_id in ranked_items if groups[item_id]]
        if not available:
            break
        below_cap = [
            item_id
            for item_id in available
            if selected_by_item[item_id] < soft_cap
        ]
        pool = below_cap or available
        rank = {item_id: index for index, item_id in enumerate(ranked_items)}
        item_id = min(
            pool,
            key=lambda value: (selected_by_item[value], rank[value], value),
        )
        selected.append(groups[item_id].pop())
        selected_by_item[item_id] += 1

    if len(selected) != question_count:
        raise AssertionError("SMART selection did not fill the requested count")
    rng.shuffle(selected)
    return SmartSelectionResult(
        tuple(selected), "SMART", question_count, len(unique)
    )


def _deduplicate(
    candidates: Sequence[SmartQuestionCandidate],
) -> list[SmartQuestionCandidate]:
    unique: dict[int, SmartQuestionCandidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.question_id, candidate)
    return list(unique.values())


def _round_robin(
    item_ids: Sequence[int],
    groups: dict[int, list[int]],
    selected_by_item: dict[int, int],
    selected: list[int],
    question_count: int,
    soft_cap: int,
) -> None:
    while len(selected) < question_count:
        progressed = False
        for item_id in item_ids:
            if len(selected) >= question_count:
                return
            if not groups[item_id] or selected_by_item[item_id] >= soft_cap:
                continue
            selected.append(groups[item_id].pop())
            selected_by_item[item_id] += 1
            progressed = True
        if not progressed:
            return


def _item_order(
    candidate: SmartQuestionCandidate,
    classification: str,
    as_of: datetime,
) -> tuple[object, ...]:
    return weak_area_order_key(
        classification=classification,
        entity_id=candidate.learning_item_id,
        mastery_score=candidate.mastery_score,
        total_attempts=candidate.total_attempts,
        last_attempted_at=None,
        next_review_at=candidate.next_review_at,
        as_of=as_of,
    )
