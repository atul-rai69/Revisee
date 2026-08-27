from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.exceptions import ApplicationError, ResourceNotFoundError
from src.modules.mastery import repository as mastery_repository
from src.modules.mastery.calculation import (
    MasteryBatch,
    MasteryContribution,
    aggregate_contributions,
    calculate_mastery_delta,
    quantize_hundredth,
)
from src.modules.mastery.service import apply_mastery_batches
from src.modules.revisions import submission_repository as repository
from src.modules.revisions.models import RevisionSessionQuestion, UserAttempt
from src.modules.revisions.submission_repository import QuestionStatisticsUpdate
from src.modules.revisions.submission_schemas import (
    AnswerOption,
    CompletedRevisionLabelResponse,
    CompletedRevisionOptionResponse,
    CompletedRevisionQuestionResponse,
    RevisionAnswerSubmission,
    RevisionSessionResultResponse,
    RevisionSessionSubmitRequest,
)


class RevisionSubmissionError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def answer_set_mismatch() -> RevisionSubmissionError:
    return RevisionSubmissionError(
        "ANSWER_SET_MISMATCH",
        "Submit exactly one answer for every session question.",
        422,
    )


def already_completed() -> RevisionSubmissionError:
    return RevisionSubmissionError(
        "REVISION_SESSION_ALREADY_COMPLETED",
        "Revision session has already been completed.",
        409,
    )


def not_completed() -> RevisionSubmissionError:
    return RevisionSubmissionError(
        "REVISION_SESSION_NOT_COMPLETED",
        "Revision session has not been completed.",
        409,
    )


def result_unavailable() -> RevisionSubmissionError:
    return RevisionSubmissionError(
        "REVISION_SESSION_RESULT_UNAVAILABLE",
        "Revision session result is unavailable.",
        409,
    )


def normalize_snapshot_answer(value: str) -> AnswerOption:
    normalized = value.strip().upper()
    if normalized in {"0", "1", "2", "3"}:
        return ("A", "B", "C", "D")[int(normalized)]
    if normalized in {"A", "B", "C", "D"}:
        return normalized  # type: ignore[return-value]
    raise result_unavailable()


@dataclass(frozen=True, slots=True)
class GradedAnswer:
    session_question: RevisionSessionQuestion
    submitted: RevisionAnswerSubmission
    correct_option: AnswerOption
    is_correct: bool
    mastery_delta: Decimal


class RevisionSubmissionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def submit(
        self,
        user_id: int,
        session_id: int,
        request: RevisionSessionSubmitRequest,
    ) -> RevisionSessionResultResponse:
        try:
            session = repository.find_owned_session_for_update(
                self.db,
                session_id,
                user_id,
            )
            if not session:
                raise ResourceNotFoundError("Revision session not found")
            if session.status == "COMPLETED":
                raise already_completed()
            if session.status != "IN_PROGRESS":
                raise result_unavailable()

            session_questions = repository.list_session_questions(self.db, session.id)
            self._validate_session_integrity(session.requested_question_count, session_questions)
            submissions = {answer.session_question_id: answer for answer in request.answers}
            if set(submissions) != {question.id for question in session_questions}:
                raise answer_set_mismatch()

            graded = [
                self._grade(question, submissions[question.id])
                for question in session_questions
            ]
            submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)

            item_ids = sorted(
                {
                    answer.session_question.learning_item_id
                    for answer in graded
                    if answer.session_question.learning_item_id is not None
                }
            )
            owned_items = repository.lock_owned_learning_items(
                self.db,
                user_id,
                item_ids,
            )
            question_ids = sorted(
                {
                    answer.session_question.question_id
                    for answer in graded
                    if answer.session_question.question_id is not None
                }
            )
            owned_questions = repository.lock_owned_questions(
                self.db,
                user_id,
                question_ids,
            )
            labels_by_item = repository.lock_current_labels_by_item(
                self.db,
                user_id,
                sorted(owned_items),
            )

            item_batches, label_batches = self._mastery_batches(
                graded,
                set(owned_items),
                labels_by_item,
            )
            mastery_repository.materialize_item_mastery(
                self.db,
                user_id,
                sorted(item_batches),
            )
            mastery_repository.materialize_label_mastery(
                self.db,
                user_id,
                sorted(label_batches),
            )
            item_mastery_rows = mastery_repository.lock_item_mastery(
                self.db,
                user_id,
                sorted(item_batches),
            )
            label_mastery_rows = mastery_repository.lock_label_mastery(
                self.db,
                user_id,
                sorted(label_batches),
            )

            attempts = [
                UserAttempt(
                    user_id=user_id,
                    session_id=session.id,
                    session_question_id=answer.session_question.id,
                    question_id=(
                        answer.session_question.question_id
                        if answer.session_question.question_id in owned_questions
                        else None
                    ),
                    selected_option=answer.submitted.selected_option,
                    is_correct=answer.is_correct,
                    time_taken_seconds=answer.submitted.time_taken_seconds,
                    mastery_delta=answer.mastery_delta,
                    attempted_at=submitted_at,
                )
                for answer in graded
            ]
            repository.add_attempts(self.db, attempts)
            repository.upsert_question_statistics(
                self.db,
                self._statistics_updates(graded, set(owned_questions)),
                submitted_at,
            )
            apply_mastery_batches(
                {row.learning_item_id: row for row in item_mastery_rows},
                item_batches,
                submitted_at,
            )
            apply_mastery_batches(
                {row.label_id: row for row in label_mastery_rows},
                label_batches,
                submitted_at,
            )

            session.status = "COMPLETED"
            session.ended_at = submitted_at
            repository.flush(self.db)
            labels = repository.list_session_labels(self.db, session.id)
            response = self._result_response(
                session,
                labels,
                session_questions,
                attempts,
            )
            self.db.commit()
            return response
        except (ResourceNotFoundError, RevisionSubmissionError):
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise ApplicationError("Revision session submission failed") from exc

    def result(self, user_id: int, session_id: int) -> RevisionSessionResultResponse:
        try:
            session = repository.find_owned_session(self.db, session_id, user_id)
            if not session:
                raise ResourceNotFoundError("Revision session not found")
            if session.status != "COMPLETED":
                raise not_completed()
            questions = repository.list_session_questions(self.db, session.id)
            labels = repository.list_session_labels(self.db, session.id)
            attempts = repository.list_session_attempts(self.db, session.id, user_id)
            return self._result_response(session, labels, questions, attempts)
        except (ResourceNotFoundError, RevisionSubmissionError):
            raise
        except Exception as exc:
            self.db.rollback()
            raise ApplicationError("Revision session result could not be loaded") from exc

    @staticmethod
    def _validate_session_integrity(
        expected_count: int,
        questions: list[RevisionSessionQuestion],
    ) -> None:
        if expected_count != len(questions) or not questions:
            raise result_unavailable()
        if len({question.id for question in questions}) != len(questions):
            raise result_unavailable()

    @staticmethod
    def _grade(
        question: RevisionSessionQuestion,
        submitted: RevisionAnswerSubmission,
    ) -> GradedAnswer:
        correct_option = normalize_snapshot_answer(question.correct_option_snapshot)
        is_correct = submitted.selected_option == correct_option
        try:
            delta = calculate_mastery_delta(
                is_correct,
                question.difficulty_snapshot,
                question.expected_time_seconds_snapshot,
                submitted.time_taken_seconds,
            )
        except ValueError as exc:
            raise result_unavailable() from exc
        return GradedAnswer(question, submitted, correct_option, is_correct, delta)

    @staticmethod
    def _mastery_batches(
        graded: list[GradedAnswer],
        surviving_item_ids: set[int],
        labels_by_item: dict[int, tuple[int, ...]],
    ) -> tuple[dict[int, MasteryBatch], dict[int, MasteryBatch]]:
        item_contributions: dict[int, list[MasteryContribution]] = defaultdict(list)
        label_contributions: dict[int, list[MasteryContribution]] = defaultdict(list)
        for answer in graded:
            item_id = answer.session_question.learning_item_id
            if item_id is None or item_id not in surviving_item_ids:
                continue
            contribution = MasteryContribution(answer.mastery_delta, answer.is_correct)
            item_contributions[item_id].append(contribution)
            for label_id in labels_by_item.get(item_id, ()):
                label_contributions[label_id].append(contribution)
        return (
            {
                entity_id: aggregate_contributions(contributions)
                for entity_id, contributions in item_contributions.items()
            },
            {
                entity_id: aggregate_contributions(contributions)
                for entity_id, contributions in label_contributions.items()
            },
        )

    @staticmethod
    def _statistics_updates(
        graded: list[GradedAnswer],
        surviving_question_ids: set[int],
    ) -> dict[int, QuestionStatisticsUpdate]:
        grouped: dict[int, list[GradedAnswer]] = defaultdict(list)
        for answer in graded:
            question_id = answer.session_question.question_id
            if question_id is not None and question_id in surviving_question_ids:
                grouped[question_id].append(answer)
        return {
            question_id: QuestionStatisticsUpdate(
                total_attempt_count=len(answers),
                correct_attempt_count=sum(answer.is_correct for answer in answers),
                total_time_seconds=sum(
                    answer.submitted.time_taken_seconds for answer in answers
                ),
            )
            for question_id, answers in grouped.items()
        }

    @staticmethod
    def _result_response(
        session,
        labels,
        questions: list[RevisionSessionQuestion],
        attempts: list[UserAttempt],
    ) -> RevisionSessionResultResponse:
        if session.status != "COMPLETED" or session.ended_at is None:
            raise result_unavailable()
        if session.requested_question_count != len(questions):
            raise result_unavailable()
        attempts_by_question = {attempt.session_question_id: attempt for attempt in attempts}
        if len(attempts_by_question) != len(attempts) or set(attempts_by_question) != {
            question.id for question in questions
        }:
            raise result_unavailable()

        result_questions: list[CompletedRevisionQuestionResponse] = []
        for question in questions:
            attempt = attempts_by_question[question.id]
            correct_option = normalize_snapshot_answer(question.correct_option_snapshot)
            expected_correctness = attempt.selected_option == correct_option
            try:
                expected_delta = calculate_mastery_delta(
                    expected_correctness,
                    question.difficulty_snapshot,
                    question.expected_time_seconds_snapshot,
                    attempt.time_taken_seconds,
                )
            except ValueError as exc:
                raise result_unavailable() from exc
            if (
                attempt.is_correct != expected_correctness
                or Decimal(attempt.mastery_delta) != expected_delta
            ):
                raise result_unavailable()
            result_questions.append(
                CompletedRevisionQuestionResponse(
                    session_question_id=question.id,
                    position=question.question_order,
                    learning_item_title=question.learning_item_title_snapshot,
                    question=question.question_text_snapshot,
                    options=[
                        CompletedRevisionOptionResponse(
                            label="A", text=question.option_a_snapshot
                        ),
                        CompletedRevisionOptionResponse(
                            label="B", text=question.option_b_snapshot
                        ),
                        CompletedRevisionOptionResponse(
                            label="C", text=question.option_c_snapshot
                        ),
                        CompletedRevisionOptionResponse(
                            label="D", text=question.option_d_snapshot
                        ),
                    ],
                    selected_option=attempt.selected_option,
                    correct_option=correct_option,
                    is_correct=expected_correctness,
                    explanation=question.explanation_snapshot,
                    difficulty=question.difficulty_snapshot,
                    expected_time_seconds=question.expected_time_seconds_snapshot,
                    time_taken_seconds=attempt.time_taken_seconds,
                    mastery_delta=Decimal(attempt.mastery_delta),
                )
            )
        correct_count = sum(question.is_correct for question in result_questions)
        question_count = len(result_questions)
        score = quantize_hundredth(
            Decimal(correct_count) * Decimal("100") / Decimal(question_count)
        )
        return RevisionSessionResultResponse(
            session_id=session.id,
            status="COMPLETED",
            requested_strategy=session.requested_strategy,
            strategy_used=session.strategy_used,
            started_at=session.started_at,
            completed_at=session.ended_at,
            question_count=question_count,
            correct_count=correct_count,
            incorrect_count=question_count - correct_count,
            score_percentage=score,
            total_time_taken_seconds=sum(
                question.time_taken_seconds for question in result_questions
            ),
            labels=(
                [
                    CompletedRevisionLabelResponse(
                        label_id=label.label_id,
                        label_name=label.label_name_snapshot,
                        question_quota=label.question_quota,
                    )
                    for label in labels
                ]
                if labels
                else None
            ),
            questions=result_questions,
        )
