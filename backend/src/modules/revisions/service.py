import json
import random
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.core.exceptions import ProviderOutputError, ResourceNotFoundError
from src.integrations.ai.base import AIProvider
from src.modules.labels.models import Label
from src.modules.learning_items import repository as learning_item_repository
from src.modules.revisions import repository
from src.modules.revisions.prompt import build_revision_prompt
from src.modules.revisions.schemas import GeneratedRevisionResponse
from src.modules.revisions.models import (
    RevisionSession,
    RevisionSessionLabel,
    RevisionSessionQuestion,
)
from src.modules.revisions.schemas import (
    LabelRevisionSessionRequest,
    RandomRevisionSessionRequest,
    RevisionSessionLabelResponse,
    RevisionSessionOptionResponse,
    RevisionSessionQuestionResponse,
    RevisionSessionRequest,
    RevisionSessionResponse,
    SmartRevisionSessionRequest,
)
from src.modules.revisions.selection import (
    LabelShortage,
    Randomizer,
    select_label_questions,
    select_random_question_ids,
)
from src.modules.revisions.smart_selection import select_smart_question_ids


class RevisionService:
    def __init__(self, db: Session, provider: AIProvider) -> None:
        self.db = db
        self.provider = provider

    def generate_content(self, title: str, description: str) -> GeneratedRevisionResponse:
        raw_content = self.provider.generate(build_revision_prompt(title, description))
        try:
            decoded = json.loads(raw_content)
            return GeneratedRevisionResponse.model_validate(decoded)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise ProviderOutputError("Revision provider returned invalid data") from exc

    def generate_for_owned_item(
        self,
        user_id: int,
        learning_item_id: int,
        title: str,
        description: str,
    ) -> dict[str, str]:
        learning_item = learning_item_repository.find_owned(
            self.db,
            learning_item_id,
            user_id,
        )
        if not learning_item:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")

        self.db.rollback()
        content = self.generate_content(title, description)

        learning_item = learning_item_repository.find_owned(
            self.db,
            learning_item_id,
            user_id,
        )
        if not learning_item:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")

        repository.add_generated_content(self.db, learning_item, content)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"message": "Revision content generated successfully."}


class InsufficientQuestionBankError(Exception):
    def __init__(self, detail: dict[str, Any]) -> None:
        super().__init__("Insufficient stored questions")
        self.detail = detail


class RevisionSessionService:
    def __init__(
        self,
        db: Session,
        randomizer: Randomizer | None = None,
    ) -> None:
        self.db = db
        self.randomizer = randomizer or random.Random()

    def create(
        self,
        user_id: int,
        request: RevisionSessionRequest,
    ) -> RevisionSessionResponse:
        try:
            if isinstance(request, RandomRevisionSessionRequest):
                response = self._create_random(user_id, request)
            elif isinstance(request, LabelRevisionSessionRequest):
                response = self._create_label(user_id, request)
            elif isinstance(request, SmartRevisionSessionRequest):
                response = self._create_smart(user_id, request)
            else:
                raise TypeError("Unsupported revision-session request")
            self.db.commit()
            return response
        except Exception:
            self.db.rollback()
            raise

    def resume(self, user_id: int, session_id: int) -> RevisionSessionResponse:
        session = repository.find_owned_session(self.db, session_id, user_id)
        if not session:
            self.db.rollback()
            raise ResourceNotFoundError("Revision session not found")
        labels = repository.list_session_labels(self.db, session.id)
        questions = repository.list_session_questions(self.db, session.id)
        return self._response(session, labels, questions)

    def _create_random(
        self,
        user_id: int,
        request: RandomRevisionSessionRequest,
    ) -> RevisionSessionResponse:
        candidates = repository.list_owned_eligible_candidates(self.db, user_id)
        question_ids, shortage = select_random_question_ids(
            candidates,
            request.question_count,
            self.randomizer,
        )
        if shortage:
            raise InsufficientQuestionBankError(
                {
                    "code": "INSUFFICIENT_QUESTION_BANK",
                    "requested_question_count": request.question_count,
                    "assignable_question_count": len(candidates),
                    "total_shortage": shortage,
                    "label_shortages": None,
                    "ai_generation_available": False,
                }
            )
        return self._persist_session(
            user_id=user_id,
            requested_strategy="RANDOM",
            question_count=request.question_count,
            questions_per_label=None,
            allow_ai_generation=request.allow_ai_generation,
            ordered_assignments=[(question_id, None) for question_id in question_ids],
            labels=[],
        )

    def _create_label(
        self,
        user_id: int,
        request: LabelRevisionSessionRequest,
    ) -> RevisionSessionResponse:
        owned_labels = repository.find_owned_labels(
            self.db,
            user_id,
            request.label_ids,
        )
        labels_by_id = {label.id: label for label in owned_labels}
        if set(labels_by_id) != set(request.label_ids):
            raise ResourceNotFoundError("Label not found")

        candidates = repository.list_owned_eligible_label_candidates(
            self.db,
            user_id,
            request.label_ids,
        )
        selection = select_label_questions(
            candidates,
            request.label_ids,
            request.questions_per_label,
            self.randomizer,
        )
        if not selection.complete:
            raise InsufficientQuestionBankError(
                self._label_shortage_detail(request.question_count, selection.shortages)
            )

        ordered_labels = [labels_by_id[label_id] for label_id in request.label_ids]
        return self._persist_session(
            user_id=user_id,
            requested_strategy="LABEL",
            question_count=request.question_count,
            questions_per_label=request.questions_per_label,
            allow_ai_generation=request.allow_ai_generation,
            ordered_assignments=[
                (assignment.question_id, assignment.label_id)
                for assignment in selection.ordered_questions
            ],
            labels=ordered_labels,
        )

    def _create_smart(
        self,
        user_id: int,
        request: SmartRevisionSessionRequest,
    ) -> RevisionSessionResponse:
        as_of = datetime.now(timezone.utc).replace(tzinfo=None)
        candidates = repository.list_owned_eligible_smart_candidates(
            self.db,
            user_id,
        )
        selection = select_smart_question_ids(
            candidates,
            request.question_count,
            as_of,
            self.randomizer,
        )
        if selection.shortage:
            raise InsufficientQuestionBankError(
                {
                    "code": "INSUFFICIENT_QUESTION_BANK",
                    "requested_question_count": request.question_count,
                    "assignable_question_count": selection.assignable_question_count,
                    "total_shortage": selection.shortage,
                    "label_shortages": None,
                    "ai_generation_available": False,
                }
            )
        return self._persist_session(
            user_id=user_id,
            requested_strategy="SMART",
            strategy_used=selection.strategy_used,
            question_count=request.question_count,
            questions_per_label=None,
            allow_ai_generation=request.allow_ai_generation,
            ordered_assignments=[
                (question_id, None) for question_id in selection.question_ids
            ],
            labels=[],
        )

    def _persist_session(
        self,
        *,
        user_id: int,
        requested_strategy: str,
        question_count: int,
        questions_per_label: int | None,
        allow_ai_generation: bool,
        ordered_assignments: list[tuple[int, int | None]],
        labels: list[Label],
        strategy_used: str | None = None,
    ) -> RevisionSessionResponse:
        question_ids = [question_id for question_id, _ in ordered_assignments]
        owned_questions = repository.find_owned_questions_by_ids(
            self.db,
            user_id,
            question_ids,
        )
        if len(owned_questions) != len(question_ids):
            raise ResourceNotFoundError("Question not found")

        session = RevisionSession(
            user_id=user_id,
            quiz_type=requested_strategy,
            requested_strategy=requested_strategy,
            strategy_used=strategy_used or requested_strategy,
            status="IN_PROGRESS",
            requested_question_count=question_count,
            questions_per_label=questions_per_label,
            generated_question_count=0,
            allow_ai_generation=allow_ai_generation,
        )
        repository.add_session(self.db, session)
        repository.flush(self.db)

        session_labels: list[RevisionSessionLabel] = []
        if labels and questions_per_label is None:
            raise ValueError("LABEL persistence requires questions_per_label")
        for label_order, label in enumerate(labels, start=1):
            session_label = RevisionSessionLabel(
                session_id=session.id,
                label_id=label.id,
                label_name_snapshot=label.label_name,
                label_order=label_order,
                question_quota=questions_per_label,
            )
            repository.add_session_label(self.db, session_label)
            session_labels.append(session_label)
        repository.flush(self.db)
        session_label_by_source_id = {
            session_label.label_id: session_label
            for session_label in session_labels
            if session_label.label_id is not None
        }

        session_questions: list[RevisionSessionQuestion] = []
        for question_order, (question_id, assigned_label_id) in enumerate(
            ordered_assignments,
            start=1,
        ):
            question, learning_item = owned_questions[question_id]
            assigned_session_label = (
                session_label_by_source_id.get(assigned_label_id)
                if assigned_label_id is not None
                else None
            )
            session_question = RevisionSessionQuestion(
                session_id=session.id,
                question_id=question.id,
                learning_item_id=learning_item.id,
                session_label_id=(
                    assigned_session_label.id if assigned_session_label else None
                ),
                question_order=question_order,
                learning_item_title_snapshot=learning_item.title,
                question_text_snapshot=question.question_text,
                option_a_snapshot=question.option_a,
                option_b_snapshot=question.option_b,
                option_c_snapshot=question.option_c,
                option_d_snapshot=question.option_d,
                correct_option_snapshot=question.correct_option,
                explanation_snapshot=question.explanation,
                difficulty_snapshot=question.difficulty,
                expected_time_seconds_snapshot=question.expected_time_seconds,
                source_snapshot=question.source,
                generated_for_session=False,
            )
            repository.add_session_question(self.db, session_question)
            session_questions.append(session_question)
        repository.flush(self.db)
        return self._response(session, session_labels, session_questions)

    @staticmethod
    def _label_shortage_detail(
        requested_question_count: int,
        shortages: tuple[LabelShortage, ...],
    ) -> dict[str, Any]:
        assignable = sum(shortage.assigned for shortage in shortages)
        return {
            "code": "INSUFFICIENT_QUESTION_BANK",
            "requested_question_count": requested_question_count,
            "assignable_question_count": assignable,
            "total_shortage": requested_question_count - assignable,
            "label_shortages": [
                {
                    "label_id": shortage.label_id,
                    "requested": shortage.requested,
                    "eligible_unique": shortage.eligible_unique,
                    "assigned": shortage.assigned,
                    "shortage": shortage.shortage,
                }
                for shortage in shortages
            ],
            "ai_generation_available": False,
        }

    @staticmethod
    def _response(
        session: RevisionSession,
        labels: list[RevisionSessionLabel],
        questions: list[RevisionSessionQuestion],
    ) -> RevisionSessionResponse:
        return RevisionSessionResponse(
            session_id=session.id,
            requested_strategy=session.requested_strategy,
            strategy_used=session.strategy_used,
            question_count=session.requested_question_count,
            questions_per_label=session.questions_per_label,
            generated_question_count=session.generated_question_count,
            status=session.status,
            labels=(
                [
                    RevisionSessionLabelResponse(
                        label_id=label.label_id,
                        label_name=label.label_name_snapshot,
                        question_quota=label.question_quota,
                    )
                    for label in labels
                ]
                if labels
                else None
            ),
            questions=[
                RevisionSessionQuestionResponse(
                    session_question_id=question.id,
                    position=question.question_order,
                    question=question.question_text_snapshot,
                    options=[
                        RevisionSessionOptionResponse(
                            label="A", text=question.option_a_snapshot
                        ),
                        RevisionSessionOptionResponse(
                            label="B", text=question.option_b_snapshot
                        ),
                        RevisionSessionOptionResponse(
                            label="C", text=question.option_c_snapshot
                        ),
                        RevisionSessionOptionResponse(
                            label="D", text=question.option_d_snapshot
                        ),
                    ],
                    difficulty=question.difficulty_snapshot,
                    expected_time_seconds=question.expected_time_seconds_snapshot,
                )
                for question in questions
            ],
        )
