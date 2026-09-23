from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from time import monotonic

from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.exceptions import (
    ApplicationError,
    DomainValidationError,
    InvalidProviderCredentialError,
    ProviderBusyError,
    ProviderOutputError,
    ProviderQuotaError,
    ProviderUnavailableError,
    ResourceNotFoundError,
)
from src.integrations.ai.base import (
    AIOperation,
    AIProvider,
    AIUsage,
    StructuredAIRequest,
    StructuredAIResult,
)
from src.modules.ai_generation import repository as generation_repository
from src.modules.ai_generation.models import AIGenerationCall, AIGenerationEvent
from src.modules.revisions import repository as question_repository
from src.modules.revisions.generation.fingerprint import (
    deduplicate_questions,
    question_fingerprint,
)
from src.modules.revisions.generation.prompt import (
    QUESTION_PROMPT_TEMPLATE_VERSION,
    build_question_prompt,
    calculate_max_output_tokens,
)
from src.modules.revisions.generation.schemas import parse_question_response
from src.modules.revisions.generation.source import (
    SourceContentUnavailableError,
    SourceBudgets,
    prepare_question_source,
)


@dataclass(frozen=True, slots=True)
class QuestionGenerationResult:
    event_id: int
    call_id: int
    status: str
    requested_count: int
    valid_count: int
    persisted_question_ids: tuple[int, ...]
    duplicate_count: int
    rejected_count: int
    excess_count: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class QuestionGenerationService:
    """Owns the short transactions around one provider call for one item."""

    def __init__(
        self,
        db: Session,
        provider: AIProvider,
        settings: Settings,
    ) -> None:
        self.db = db
        self.provider = provider
        self.settings = settings

    def generate_for_owned_item(
        self,
        *,
        user_id: int,
        learning_item_id: int,
        question_count: int,
        operation: AIOperation,
        call_order: int = 1,
        personal_remarks: str | None = None,
        credential_id: int | None = None,
    ) -> QuestionGenerationResult:
        self._validate_request(question_count, call_order)
        source_record = generation_repository.find_owned_source(
            self.db,
            user_id,
            learning_item_id,
        )
        if source_record is None:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")

        try:
            source = prepare_question_source(
                title=source_record.title,
                theory=source_record.theory,
                key_points=source_record.key_points,
                description_text=source_record.description_text,
                budgets=SourceBudgets(
                    maximum_source_characters=(
                        self.settings.AI_MAX_SOURCE_CHARACTERS
                    ),
                    maximum_theory_characters=(
                        self.settings.AI_MAX_THEORY_CHARACTERS
                    ),
                    maximum_key_point_characters=(
                        self.settings.AI_MAX_KEY_POINT_CHARACTERS
                    ),
                    maximum_notes_characters=(
                        self.settings.AI_MAX_NOTES_CHARACTERS
                    ),
                ),
            )
        except SourceContentUnavailableError as exc:
            self.db.rollback()
            raise DomainValidationError(
                "Learning item has no usable generation source"
            ) from exc
        prompt = build_question_prompt(
            source,
            question_count,
            self.settings.AI_MAX_PROMPT_CHARACTERS,
            personal_remarks,
        )
        self.db.rollback()

        event_id, call_id = self._create_event_and_call(
            user_id=user_id,
            learning_item_id=learning_item_id,
            operation=operation,
            question_count=question_count,
            call_order=call_order,
            source_identifier=source.source_identifier,
            credential_id=credential_id,
        )
        self._mark_processing(event_id, call_id)

        request = StructuredAIRequest(
            prompt=prompt,
            operation=operation,
            max_output_tokens=calculate_max_output_tokens(
                question_count,
                self.settings.AI_MAX_OUTPUT_TOKENS,
            ),
        )
        started = monotonic()
        try:
            provider_result = self.provider.generate_structured(request)
        except InvalidProviderCredentialError:
            self._record_failure(event_id, call_id, "AI_CREDENTIAL_INVALID", prompt)
            raise
        except ProviderQuotaError:
            self._record_failure(event_id, call_id, "AI_PROVIDER_QUOTA", prompt)
            raise
        except ProviderBusyError:
            self._record_failure(event_id, call_id, "AI_PROVIDER_BUSY", prompt)
            raise
        except ProviderUnavailableError:
            self._record_failure(
                event_id,
                call_id,
                "AI_PROVIDER_FAILURE",
                prompt,
            )
            raise
        except Exception as exc:
            self._record_failure(
                event_id,
                call_id,
                "AI_PROVIDER_FAILURE",
                prompt,
            )
            raise ProviderUnavailableError(
                "Revision provider is unavailable"
            ) from exc

        if monotonic() - started > self.settings.AI_OPERATION_DEADLINE_SECONDS:
            self._record_failure(
                event_id,
                call_id,
                "AI_OPERATION_DEADLINE_EXCEEDED",
                prompt,
                provider_result,
            )
            raise ProviderUnavailableError("Revision provider is unavailable")

        try:
            parsed = parse_question_response(
                provider_result.text,
                requested_count=question_count,
                maximum_response_characters=(
                    self.settings.AI_MAX_RAW_RESPONSE_CHARACTERS
                ),
                maximum_expected_time_seconds=(
                    self.settings.AI_MAX_EXPECTED_TIME_SECONDS
                ),
            )
        except ProviderOutputError:
            self._record_failure(
                event_id,
                call_id,
                "AI_INVALID_OUTPUT",
                prompt,
                provider_result,
            )
            raise

        if not parsed.questions:
            self._record_failure(
                event_id,
                call_id,
                "AI_INVALID_OUTPUT",
                prompt,
                provider_result,
                rejected_count=parsed.rejected_count,
                excess_count=parsed.excess_count,
            )
            raise ProviderOutputError("Revision provider returned invalid data")

        try:
            current_source = generation_repository.find_owned_source(
                self.db,
                user_id,
                learning_item_id,
            )
            if current_source is None:
                self.db.rollback()
                self._record_failure(
                    event_id,
                    call_id,
                    "SOURCE_NOT_FOUND",
                    prompt,
                    provider_result,
                )
                raise ResourceNotFoundError("Learning item not found")

            existing = question_repository.list_question_fingerprint_inputs(
                self.db,
                learning_item_id,
            )
            existing_fingerprints = {
                row.stored_fingerprint
                or question_fingerprint(row.question_text, row.options)
                for row in existing
            }
            deduplicated = deduplicate_questions(
                parsed.questions,
                existing_fingerprints,
            )
            inserted = question_repository.insert_generated_questions_conflict_safe(
                self.db,
                [
                    {
                        "learning_item_id": learning_item_id,
                        "question_text": entry.question.question,
                        "option_a": entry.question.options[0],
                        "option_b": entry.question.options[1],
                        "option_c": entry.question.options[2],
                        "option_d": entry.question.options[3],
                        "correct_option": entry.question.correct_answer,
                        "explanation": entry.question.explanation,
                        "difficulty": entry.question.difficulty_level,
                        "expected_time_seconds": (
                            entry.question.expected_time_seconds
                        ),
                        "source": "ai-question-v1",
                        "content_fingerprint": entry.fingerprint,
                        "generation_event_id": event_id,
                    }
                    for entry in deduplicated.questions
                ],
            )
            concurrent_duplicate_count = len(deduplicated.questions) - len(inserted)
            duplicate_count = (
                deduplicated.duplicate_count + concurrent_duplicate_count
            )
            status = "COMPLETED" if len(inserted) == question_count else "PARTIAL"
            self._finalize_success(
                event_id,
                call_id,
                status=status,
                valid_count=len(parsed.questions),
                persisted_count=len(inserted),
                duplicate_count=duplicate_count,
                rejected_count=parsed.rejected_count,
                excess_count=parsed.excess_count,
                prompt=prompt,
                provider_result=provider_result,
            )
            self.db.commit()
        except (ProviderOutputError, ProviderUnavailableError, ResourceNotFoundError):
            raise
        except Exception as exc:
            self.db.rollback()
            self._record_failure(
                event_id,
                call_id,
                "AI_PERSISTENCE_FAILURE",
                prompt,
                provider_result,
            )
            raise ApplicationError("Question generation could not be saved") from exc

        return QuestionGenerationResult(
            event_id=event_id,
            call_id=call_id,
            status=status,
            requested_count=question_count,
            valid_count=len(parsed.questions),
            persisted_question_ids=tuple(
                inserted[entry.fingerprint]
                for entry in deduplicated.questions
                if entry.fingerprint in inserted
            ),
            duplicate_count=duplicate_count,
            rejected_count=parsed.rejected_count,
            excess_count=parsed.excess_count,
        )

    def _validate_request(self, question_count: int, call_order: int) -> None:
        if not self.settings.AI_GENERATION_ENABLED:
            raise ProviderUnavailableError("Revision provider is unavailable")
        if not 1 <= question_count <= self.settings.AI_MAX_QUESTIONS_PER_CALL:
            raise DomainValidationError("Invalid generation question count")
        if not 1 <= call_order <= self.settings.AI_MAX_SOURCE_ITEMS_PER_OPERATION:
            raise DomainValidationError("Invalid generation call order")

    def _create_event_and_call(
        self,
        *,
        user_id: int,
        learning_item_id: int,
        operation: AIOperation,
        question_count: int,
        call_order: int,
        source_identifier: str,
        credential_id: int | None,
    ) -> tuple[int, int]:
        event = AIGenerationEvent(
            user_id=user_id,
            credential_id=credential_id,
            operation_type=operation.value,
            prompt_template_version=QUESTION_PROMPT_TEMPLATE_VERSION,
            status="PENDING",
            requested_count=question_count,
        )
        generation_repository.add_event(self.db, event)
        generation_repository.flush(self.db)
        call = AIGenerationCall(
            generation_event_id=event.id,
            learning_item_id=learning_item_id,
            source_identifier=source_identifier,
            call_order=call_order,
            allocated_count=question_count,
            status="PENDING",
        )
        generation_repository.add_call(self.db, call)
        generation_repository.flush(self.db)
        event_id = event.id
        call_id = call.id
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            raise ApplicationError("Question generation could not be recorded") from exc
        return event_id, call_id

    def _mark_processing(self, event_id: int, call_id: int) -> None:
        event, call = self._load_records(event_id, call_id)
        now = _utc_now()
        event.status = "PROCESSING"
        event.started_at = now
        call.status = "PROCESSING"
        call.started_at = now
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            raise ApplicationError("Question generation could not be recorded") from exc

    def _finalize_success(
        self,
        event_id: int,
        call_id: int,
        *,
        status: str,
        valid_count: int,
        persisted_count: int,
        duplicate_count: int,
        rejected_count: int,
        excess_count: int,
        prompt: str,
        provider_result: StructuredAIResult,
    ) -> None:
        event, call = self._load_records(event_id, call_id)
        values = {
            "status": status,
            "valid_count": valid_count,
            "persisted_count": persisted_count,
            "duplicate_count": duplicate_count,
            "rejected_count": rejected_count,
            "excess_count": excess_count,
            "completed_at": _utc_now(),
        }
        self._apply_result_metadata(event, prompt, provider_result)
        self._apply_result_metadata(call, prompt, provider_result)
        for record in (event, call):
            for name, value in values.items():
                setattr(record, name, value)

    def _record_failure(
        self,
        event_id: int,
        call_id: int,
        safe_error_code: str,
        prompt: str,
        provider_result: StructuredAIResult | None = None,
        *,
        rejected_count: int = 0,
        excess_count: int = 0,
    ) -> None:
        self.db.rollback()
        event, call = self._load_records(event_id, call_id)
        for record in (event, call):
            record.status = "FAILED"
            record.safe_error_code = safe_error_code
            record.rejected_count = rejected_count
            record.excess_count = excess_count
            record.completed_at = _utc_now()
            if provider_result is not None:
                self._apply_result_metadata(record, prompt, provider_result)
            else:
                record.estimated_input_tokens = ceil(len(prompt) / 4)
                record.input_token_count_estimated = True
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            raise ApplicationError("Question generation could not be recorded") from exc

    def _load_records(
        self,
        event_id: int,
        call_id: int,
    ) -> tuple[AIGenerationEvent, AIGenerationCall]:
        event = generation_repository.find_event(self.db, event_id)
        call = generation_repository.find_call(self.db, call_id)
        if event is None or call is None:
            raise RuntimeError("Generation operation record is missing")
        return event, call

    @staticmethod
    def _apply_result_metadata(
        record: AIGenerationEvent | AIGenerationCall,
        prompt: str,
        result: StructuredAIResult,
    ) -> None:
        usage: AIUsage = result.usage
        record.input_tokens = usage.input_tokens
        record.output_tokens = usage.output_tokens
        record.total_tokens = usage.total_tokens
        record.cached_tokens = usage.cached_tokens
        record.thought_tokens = usage.thought_tokens
        record.tool_tokens = usage.tool_tokens
        record.model = result.model
        record.response_id = result.response_id
        record.provider = result.provider
        if usage.input_tokens is None:
            record.estimated_input_tokens = ceil(len(prompt) / 4)
            record.input_token_count_estimated = True
        else:
            record.estimated_input_tokens = None
            record.input_token_count_estimated = False
