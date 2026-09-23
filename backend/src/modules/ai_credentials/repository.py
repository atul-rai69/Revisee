from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.modules.ai_credentials.models import AICredential, AICredentialUsage


@dataclass(frozen=True, slots=True)
class CredentialUsageAggregate:
    request_count: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    updated_at: datetime | None


def list_owned(db: Session, user_id: int) -> list[AICredential]:
    return (
        db.query(AICredential)
        .filter(AICredential.user_id == user_id)
        .order_by(AICredential.is_default.desc(), AICredential.created_at.asc())
        .all()
    )


def find_owned(db: Session, user_id: int, credential_id: int) -> AICredential | None:
    return (
        db.query(AICredential)
        .filter(
            AICredential.id == credential_id,
            AICredential.user_id == user_id,
        )
        .first()
    )


def add(db: Session, credential: AICredential) -> None:
    db.add(credential)


def clear_default(db: Session, user_id: int, provider: str) -> None:
    (
        db.query(AICredential)
        .filter(
            AICredential.user_id == user_id,
            AICredential.provider == provider,
            AICredential.is_default.is_(True),
        )
        .update({AICredential.is_default: False}, synchronize_session="fetch")
    )


def usage_by_credential(
    db: Session,
    user_id: int,
) -> dict[int, CredentialUsageAggregate]:
    rows = (
        db.query(
            AICredentialUsage.credential_id,
            func.count(AICredentialUsage.id),
            func.sum(AICredentialUsage.input_tokens),
            func.sum(AICredentialUsage.output_tokens),
            func.sum(AICredentialUsage.total_tokens),
            func.max(AICredentialUsage.created_at),
        )
        .filter(AICredentialUsage.user_id == user_id)
        .group_by(AICredentialUsage.credential_id)
        .all()
    )
    return {
        credential_id: CredentialUsageAggregate(
            request_count=int(request_count),
            input_tokens=int(input_tokens) if input_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
            total_tokens=int(total_tokens) if total_tokens is not None else None,
            updated_at=updated_at,
        )
        for credential_id, request_count, input_tokens, output_tokens, total_tokens, updated_at in rows
    }
