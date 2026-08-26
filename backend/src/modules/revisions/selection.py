from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol, Sequence


class Randomizer(Protocol):
    def sample(self, population: Sequence[int], k: int) -> list[int]: ...

    def shuffle(self, values: list[int]) -> None: ...


@dataclass(frozen=True)
class QuestionCandidate:
    question_id: int
    label_ids: frozenset[int] = frozenset()


@dataclass(frozen=True)
class AssignedQuestion:
    question_id: int
    label_id: int


@dataclass(frozen=True)
class LabelShortage:
    label_id: int
    requested: int
    eligible_unique: int
    assigned: int

    @property
    def shortage(self) -> int:
        return self.requested - self.assigned


@dataclass(frozen=True)
class LabelSelectionResult:
    ordered_questions: tuple[AssignedQuestion, ...]
    shortages: tuple[LabelShortage, ...]

    @property
    def complete(self) -> bool:
        return not any(shortage.shortage for shortage in self.shortages)


def select_random_question_ids(
    candidates: Sequence[QuestionCandidate],
    question_count: int,
    randomizer: Randomizer | None = None,
) -> tuple[list[int], int]:
    rng = randomizer or random.Random()
    unique_ids = list(dict.fromkeys(candidate.question_id for candidate in candidates))
    if len(unique_ids) < question_count:
        return [], question_count - len(unique_ids)
    return rng.sample(unique_ids, question_count), 0


def select_label_questions(
    candidates: Sequence[QuestionCandidate],
    label_ids: Sequence[int],
    questions_per_label: int,
    randomizer: Randomizer | None = None,
) -> LabelSelectionResult:
    rng = randomizer or random.Random()
    requested_labels = list(label_ids)
    label_order = {label_id: index for index, label_id in enumerate(requested_labels)}

    labels_by_question: dict[int, set[int]] = {}
    requested_set = set(requested_labels)
    for candidate in candidates:
        labels_by_question.setdefault(candidate.question_id, set()).update(
            candidate.label_ids & requested_set
        )

    eligible_by_label: dict[int, list[int]] = {
        label_id: [
            question_id
            for question_id, candidate_labels in labels_by_question.items()
            if label_id in candidate_labels
        ]
        for label_id in requested_labels
    }
    for question_ids in eligible_by_label.values():
        rng.shuffle(question_ids)

    constrained_labels = sorted(
        requested_labels,
        key=lambda label_id: (len(eligible_by_label[label_id]), label_order[label_id]),
    )
    slots: list[int] = [
        label_id
        for label_id in constrained_labels
        for _ in range(questions_per_label)
    ]
    question_to_slot: dict[int, int] = {}
    slot_to_question: dict[int, int] = {}

    def assign(
        slot_index: int,
        seen_questions: set[int],
        seen_slots: set[int],
    ) -> bool:
        label_id = slots[slot_index]
        for question_id in eligible_by_label[label_id]:
            if question_id in seen_questions:
                continue
            seen_questions.add(question_id)
            previous_slot = question_to_slot.get(question_id)
            if previous_slot is None or (
                previous_slot not in seen_slots
                and assign(
                    previous_slot,
                    seen_questions,
                    seen_slots | {previous_slot},
                )
            ):
                question_to_slot[question_id] = slot_index
                slot_to_question[slot_index] = question_id
                return True
        return False

    for slot_index in range(len(slots)):
        assign(slot_index, set(), {slot_index})

    assigned_by_label: dict[int, list[int]] = {
        label_id: [] for label_id in requested_labels
    }
    for slot_index, question_id in sorted(slot_to_question.items()):
        assigned_by_label[slots[slot_index]].append(question_id)

    shortages = tuple(
        LabelShortage(
            label_id=label_id,
            requested=questions_per_label,
            eligible_unique=len(eligible_by_label[label_id]),
            assigned=len(assigned_by_label[label_id]),
        )
        for label_id in requested_labels
    )

    ordered: list[AssignedQuestion] = []
    for quota_index in range(questions_per_label):
        for label_id in requested_labels:
            assigned = assigned_by_label[label_id]
            if quota_index < len(assigned):
                ordered.append(
                    AssignedQuestion(
                        question_id=assigned[quota_index],
                        label_id=label_id,
                    )
                )

    return LabelSelectionResult(tuple(ordered), shortages)
