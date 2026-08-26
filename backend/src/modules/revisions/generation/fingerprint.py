from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import re
import unicodedata

from src.modules.revisions.generation.schemas import ValidatedGeneratedQuestion


def normalize_fingerprint_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def question_fingerprint(question: str, options: Sequence[str]) -> str:
    payload = {
        "options": sorted(normalize_fingerprint_text(option) for option in options),
        "question": normalize_fingerprint_text(question),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FingerprintedQuestion:
    question: ValidatedGeneratedQuestion
    fingerprint: str


@dataclass(frozen=True, slots=True)
class DeduplicatedQuestionBatch:
    questions: tuple[FingerprintedQuestion, ...]
    duplicate_count: int
    fingerprints: frozenset[str]


def deduplicate_questions(
    questions: Iterable[ValidatedGeneratedQuestion],
    existing_fingerprints: Iterable[str] = (),
) -> DeduplicatedQuestionBatch:
    seen = set(existing_fingerprints)
    accepted: list[FingerprintedQuestion] = []
    duplicate_count = 0
    for question in questions:
        fingerprint = question_fingerprint(question.question, question.options)
        if fingerprint in seen:
            duplicate_count += 1
            continue
        seen.add(fingerprint)
        accepted.append(
            FingerprintedQuestion(question=question, fingerprint=fingerprint)
        )
    return DeduplicatedQuestionBatch(
        questions=tuple(accepted),
        duplicate_count=duplicate_count,
        fingerprints=frozenset(seen),
    )
