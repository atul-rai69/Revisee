from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.modules.revisions.submission_schemas import (
    RevisionSessionResultResponse,
    RevisionSessionSubmitRequest,
)


def test_submission_schema_is_strict_and_forbids_duplicates() -> None:
    valid = {
        "answers": [
            {
                "session_question_id": 1,
                "selected_option": "A",
                "time_taken_seconds": 0,
            }
        ]
    }
    assert RevisionSessionSubmitRequest.model_validate(valid).answers[0].selected_option == "A"

    invalid_payloads = [
        {"answers": [valid["answers"][0], valid["answers"][0]]},
        {"answers": [{**valid["answers"][0], "selected_option": "a"}]},
        {"answers": [{**valid["answers"][0], "time_taken_seconds": 3601}]},
        {"answers": [{**valid["answers"][0], "session_question_id": "1"}]},
        {"answers": [{**valid["answers"][0], "unexpected": True}]},
        {"answers": [], "unexpected": True},
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            RevisionSessionSubmitRequest.model_validate(payload)


def test_result_decimals_serialize_as_json_numbers() -> None:
    result = RevisionSessionResultResponse.model_validate(
        {
            "session_id": 1,
            "status": "COMPLETED",
            "requested_strategy": "RANDOM",
            "strategy_used": "RANDOM",
            "started_at": None,
            "completed_at": "2026-08-26T10:00:00",
            "question_count": 1,
            "correct_count": 1,
            "incorrect_count": 0,
            "score_percentage": Decimal("100.00"),
            "total_time_taken_seconds": 10,
            "labels": None,
            "questions": [
                {
                    "session_question_id": 2,
                    "position": 1,
                    "learning_item_title": "Item",
                    "question": "Q?",
                    "options": [
                        {"label": "A", "text": "A"},
                        {"label": "B", "text": "B"},
                        {"label": "C", "text": "C"},
                        {"label": "D", "text": "D"},
                    ],
                    "selected_option": "A",
                    "correct_option": "A",
                    "is_correct": True,
                    "explanation": "Because",
                    "difficulty": 1,
                    "expected_time_seconds": 20,
                    "time_taken_seconds": 10,
                    "mastery_delta": Decimal("5.00"),
                }
            ],
        }
    )
    payload = result.model_dump(mode="json")
    assert payload["score_percentage"] == 100.0
    assert payload["questions"][0]["mastery_delta"] == 5.0
