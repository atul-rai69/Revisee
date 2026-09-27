from time import monotonic

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.exceptions import (
    ApplicationError,
    DomainValidationError,
    ProviderOutputError,
    ProviderUnavailableError,
    ResourceNotFoundError,
)
from src.integrations.ai.base import AIOperation, AIProvider, StructuredAIRequest
from src.modules.learning_items import repository as learning_repository
from src.modules.learning_items.schemas import ManualQuestionCreateRequest
from src.modules.pdf_questions.grounding import (
    build_grounded_passages,
    build_pdf_question_prompt,
    normalize_evidence_text,
    page_text_map,
    parse_grounded_response,
)
from src.modules.pdf_questions.schemas import (
    PdfDraftGenerationRequest,
    PdfDraftGenerationResponse,
    PdfQuestionImportRequest,
    PdfQuestionImportResponse,
    PdfSourcePage,
)
from src.modules.revisions import repository as question_repository
from src.modules.revisions.generation.fingerprint import question_fingerprint


class PdfQuestionService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def generate_drafts(
        self,
        *,
        user_id: int,
        learning_item_id: int,
        request: PdfDraftGenerationRequest,
        provider: AIProvider,
    ) -> PdfDraftGenerationResponse:
        self._require_owned_item(user_id, learning_item_id)
        page_texts = self._validated_pages(request.source_pages)
        passages = build_grounded_passages(
            request.source_pages,
            maximum_characters=self.settings.AI_MAX_SOURCE_CHARACTERS,
            maximum_pages=self.settings.PDF_QUESTION_MAX_COVERAGE_PAGES,
        )
        if not passages.text:
            raise DomainValidationError("The selected PDF pages contain no usable text")
        prompt = build_pdf_question_prompt(
            passages,
            mode=request.mode,
            question_count=request.question_count,
            difficulty=request.difficulty,
            focus_instructions=request.focus_instructions,
        )
        if len(prompt) > self.settings.AI_MAX_PROMPT_CHARACTERS:
            raise DomainValidationError("The selected PDF text exceeds the generation limit")
        self.db.rollback()
        started = monotonic()
        result = provider.generate_structured(StructuredAIRequest(
            prompt=prompt,
            operation=AIOperation.PDF_QUESTION_DRAFTS,
            max_output_tokens=min(
                self.settings.AI_MAX_OUTPUT_TOKENS,
                max(1_200, request.question_count * 600),
            ),
        ))
        # Personal-provider usage is attached to this transaction by the
        # existing UsageRecordingProvider. Drafts remain ephemeral; only the
        # provider usage metadata and last-used timestamp are persisted here.
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            raise ApplicationError("PDF question usage could not be recorded") from exc
        if monotonic() - started > self.settings.AI_OPERATION_DEADLINE_SECONDS:
            raise ProviderUnavailableError("Revision provider is unavailable")
        parsed = parse_grounded_response(
            result.text,
            requested_count=request.question_count,
            page_texts={
                page_number: page_texts[page_number]
                for page_number in passages.page_numbers
            },
            maximum_response_characters=self.settings.AI_MAX_RAW_RESPONSE_CHARACTERS,
        )
        return PdfDraftGenerationResponse(
            drafts=list(parsed.drafts),
            requested_count=request.question_count,
            returned_count=len(parsed.drafts),
            rejected_count=parsed.rejected_count,
            partial=len(parsed.drafts) < request.question_count,
            coverage_page_numbers=list(passages.page_numbers),
        )

    def import_questions(
        self,
        *,
        user_id: int,
        source_learning_item_id: int,
        request: PdfQuestionImportRequest,
    ) -> PdfQuestionImportResponse:
        self._require_owned_item(user_id, source_learning_item_id)
        destination = learning_repository.find_owned(
            self.db, request.destination_learning_item_id, user_id
        )
        if destination is None:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")
        page_texts = self._validated_pages(request.source_pages)
        if len(request.questions) > self.settings.PDF_QUESTION_MAX_IMPORT_COUNT:
            raise DomainValidationError("Too many questions were selected for import")

        existing = question_repository.list_question_fingerprint_inputs(
            self.db, destination.id
        )
        seen = {
            row.stored_fingerprint
            or question_fingerprint(row.question_text, row.options)
            for row in existing
        }
        values: list[dict[str, object]] = []
        duplicate_count = 0
        rejected_count = 0
        for draft in request.questions:
            try:
                excerpt = normalize_evidence_text(draft.source_excerpt)
                source = page_texts.get(draft.source_page)
                if not source or not excerpt or excerpt not in source:
                    rejected_count += 1
                    continue
                options = draft.options.as_tuple()
                validated = ManualQuestionCreateRequest.model_validate({
                    "question": draft.question,
                    "option_a": options[0],
                    "option_b": options[1],
                    "option_c": options[2],
                    "option_d": options[3],
                    "correct_option": draft.correct_option,
                    "explanation": draft.explanation,
                    "difficulty": draft.difficulty,
                    "expected_time_seconds": draft.expected_time_seconds,
                })
                validated_options = (
                    validated.option_a,
                    validated.option_b,
                    validated.option_c,
                    validated.option_d,
                )
                fingerprint = question_fingerprint(
                    validated.question, validated_options
                )
                if fingerprint in seen:
                    duplicate_count += 1
                    continue
                seen.add(fingerprint)
                values.append({
                    "learning_item_id": destination.id,
                    "question_text": validated.question,
                    "option_a": validated.option_a,
                    "option_b": validated.option_b,
                    "option_c": validated.option_c,
                    "option_d": validated.option_d,
                    "correct_option": {"A": "0", "B": "1", "C": "2", "D": "3"}[
                        validated.correct_option
                    ],
                    "explanation": validated.explanation,
                    "difficulty": validated.difficulty,
                    "expected_time_seconds": validated.expected_time_seconds,
                    "source": "pdf-import",
                    "content_fingerprint": fingerprint,
                    "generation_event_id": None,
                })
            except (ValidationError, TypeError, ValueError):
                rejected_count += 1

        try:
            inserted = question_repository.insert_generated_questions_conflict_safe(
                self.db, values
            )
            duplicate_count += len(values) - len(inserted)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ApplicationError("PDF questions could not be imported") from exc
        except Exception as exc:
            self.db.rollback()
            raise ApplicationError("PDF questions could not be imported") from exc

        return PdfQuestionImportResponse(
            inserted_count=len(inserted),
            duplicate_count=duplicate_count,
            rejected_count=rejected_count,
            failed_count=0,
            inserted_question_ids=list(inserted.values()),
        )

    def _require_owned_item(self, user_id: int, learning_item_id: int) -> None:
        item = learning_repository.find_owned(self.db, learning_item_id, user_id)
        if item is None:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")

    def _validated_pages(self, pages: list[PdfSourcePage]) -> dict[int, str]:
        if len(pages) > self.settings.PDF_QUESTION_MAX_PAGES:
            raise DomainValidationError("Too many PDF pages were submitted")
        if any(
            len(page.text) > self.settings.PDF_QUESTION_MAX_PAGE_CHARACTERS
            for page in pages
        ):
            raise DomainValidationError("A PDF page exceeds the text limit")
        if sum(len(page.text) for page in pages) > (
            self.settings.PDF_QUESTION_MAX_EXTRACTED_CHARACTERS
        ):
            raise DomainValidationError("The extracted PDF text exceeds the request limit")
        try:
            return page_text_map(pages)
        except ValueError as exc:
            raise DomainValidationError(str(exc)) from exc
