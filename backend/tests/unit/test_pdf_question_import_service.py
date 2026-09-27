from types import SimpleNamespace
import json

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.core.exceptions import (
    ApplicationError,
    InvalidProviderCredentialError,
    ProviderOutageError,
    ProviderQuotaError,
    ResourceNotFoundError,
)
from src.integrations.ai.base import AIUsage, StructuredAIResult
from src.modules.pdf_questions.schemas import (
    PdfDraftGenerationRequest,
    PdfQuestionImportRequest,
)
from src.modules.pdf_questions.service import PdfQuestionService


class _Db:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _request() -> PdfQuestionImportRequest:
    return PdfQuestionImportRequest.model_validate({
        "source_filename": "questions.pdf",
        "destination_learning_item_id": 20,
        "source_pages": [{"page_number": 1, "text": "Grounded evidence appears here."}],
        "questions": [{
            "question": "What appears in the source?",
            "options": {"A": "Grounded evidence", "B": "Two", "C": "Three", "D": "Four"},
            "correct_option": "A",
            "explanation": "The source contains grounded evidence.",
            "difficulty": 2,
            "expected_time_seconds": 30,
            "source_page": 1,
            "source_excerpt": "Grounded evidence appears here.",
            "confidence": 0.9,
            "validation_issues": [],
        }],
    })


def _settings():
    return SimpleNamespace(
        PDF_QUESTION_MAX_PAGES=50,
        PDF_QUESTION_MAX_PAGE_CHARACTERS=20_000,
        PDF_QUESTION_MAX_EXTRACTED_CHARACTERS=120_000,
        PDF_QUESTION_MAX_IMPORT_COUNT=25,
        PDF_QUESTION_MAX_COVERAGE_PAGES=12,
        AI_MAX_SOURCE_CHARACTERS=8_000,
        AI_MAX_PROMPT_CHARACTERS=12_000,
        AI_MAX_OUTPUT_TOKENS=4_800,
        AI_OPERATION_DEADLINE_SECONDS=120,
        AI_MAX_RAW_RESPONSE_CHARACTERS=40_000,
    )


@pytest.mark.parametrize("filename", ["notes.txt", "../private.pdf", "folder\\private.pdf", ""])
def test_requests_reject_invalid_untrusted_source_filenames(filename: str) -> None:
    payload = _request().model_dump()
    payload["source_filename"] = filename
    with pytest.raises(PydanticValidationError):
        PdfQuestionImportRequest.model_validate(payload)


def test_import_rolls_back_all_questions_on_unexpected_persistence_failure(monkeypatch) -> None:
    db = _Db()
    service = PdfQuestionService(db, _settings())  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_require_owned_item", lambda *_args: None)
    monkeypatch.setattr(
        "src.modules.pdf_questions.service.learning_repository.find_owned",
        lambda *_args: SimpleNamespace(id=20),
    )
    monkeypatch.setattr(
        "src.modules.pdf_questions.service.question_repository.list_question_fingerprint_inputs",
        lambda *_args: [],
    )
    monkeypatch.setattr(
        "src.modules.pdf_questions.service.question_repository.insert_generated_questions_conflict_safe",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("synthetic failure")),
    )

    with pytest.raises(ApplicationError):
        service.import_questions(
            user_id=1,
            source_learning_item_id=10,
            request=_request(),
        )
    assert db.commits == 0
    assert db.rollbacks == 1


def test_import_reports_an_existing_question_without_inserting(monkeypatch) -> None:
    db = _Db()
    service = PdfQuestionService(db, _settings())  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_require_owned_item", lambda *_args: None)
    monkeypatch.setattr(
        "src.modules.pdf_questions.service.learning_repository.find_owned",
        lambda *_args: SimpleNamespace(id=20),
    )
    request = _request()
    draft = request.questions[0]
    monkeypatch.setattr(
        "src.modules.pdf_questions.service.question_repository.list_question_fingerprint_inputs",
        lambda *_args: [SimpleNamespace(
            stored_fingerprint=None,
            question_text=draft.question,
            options=draft.options.as_tuple(),
        )],
    )
    insert = lambda _db, values: {}  # noqa: E731
    monkeypatch.setattr(
        "src.modules.pdf_questions.service.question_repository.insert_generated_questions_conflict_safe",
        insert,
    )

    result = service.import_questions(
        user_id=1,
        source_learning_item_id=10,
        request=request,
    )
    assert result.inserted_count == 0
    assert result.duplicate_count == 1
    assert db.commits == 1


def test_foreign_source_item_is_concealed_as_not_found(monkeypatch) -> None:
    db = _Db()
    service = PdfQuestionService(db, _settings())  # type: ignore[arg-type]
    monkeypatch.setattr(
        "src.modules.pdf_questions.service.learning_repository.find_owned",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(ResourceNotFoundError):
        service.import_questions(
            user_id=1,
            source_learning_item_id=10,
            request=_request(),
        )
    assert db.rollbacks == 1


@pytest.mark.parametrize(
    "provider_error",
    [InvalidProviderCredentialError(), ProviderQuotaError(), ProviderOutageError()],
)
def test_generation_propagates_classified_provider_errors_without_fallback(
    monkeypatch,
    provider_error,
) -> None:
    class _Provider:
        calls = 0

        def generate_structured(self, _request):
            self.calls += 1
            raise provider_error

    db = _Db()
    provider = _Provider()
    service = PdfQuestionService(db, _settings())  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_require_owned_item", lambda *_args: None)
    request = PdfDraftGenerationRequest.model_validate({
        "source_filename": "questions.pdf",
        "mode": "GENERATE",
        "source_pages": [{"page_number": 1, "text": "Grounded evidence appears here."}],
        "question_count": 1,
        "difficulty": 2,
        "generation_source": "PERSONAL",
        "credential_id": 4,
    })

    with pytest.raises(type(provider_error)):
        service.generate_drafts(
            user_id=1,
            learning_item_id=10,
            request=request,
            provider=provider,  # type: ignore[arg-type]
        )
    assert provider.calls == 1
    assert db.commits == 0


def test_generation_returns_ephemeral_grounded_drafts_and_commits_usage(monkeypatch) -> None:
    class _Provider:
        def generate_structured(self, _request):
            return StructuredAIResult(
                text=json.dumps({"questions": [{
                    "question": "What is grounded?",
                    "options": {"A": "Evidence", "B": "Two", "C": "Three", "D": "Four"},
                    "correct_option": "A",
                    "explanation": "The passage contains grounded evidence.",
                    "difficulty": 2,
                    "expected_time_seconds": 30,
                    "source_page": 1,
                    "source_excerpt": "Grounded evidence",
                    "confidence": 0.9,
                }]}),
                provider="gemini",
                model="test",
                response_id="response",
                usage=AIUsage(total_tokens=10),
            )

    db = _Db()
    service = PdfQuestionService(db, _settings())  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_require_owned_item", lambda *_args: None)
    result = service.generate_drafts(
        user_id=1,
        learning_item_id=10,
        request=PdfDraftGenerationRequest.model_validate({
            "source_filename": "questions.pdf",
            "mode": "GENERATE",
            "source_pages": [{"page_number": 1, "text": "Grounded evidence appears here."}],
            "question_count": 1,
            "difficulty": 2,
            "generation_source": "REVISEE",
            "credential_id": None,
        }),
        provider=_Provider(),  # type: ignore[arg-type]
    )

    assert result.returned_count == 1
    assert db.commits == 1
