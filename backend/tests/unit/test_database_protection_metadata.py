from src.modules.auth.models import UserSession
from src.modules.learning_items.models import LearningItemKeyPoint


def _only_foreign_key(column):
    foreign_keys = list(column.foreign_keys)
    assert len(foreign_keys) == 1
    return foreign_keys[0]


def test_key_point_parent_reference_is_required_and_cascades() -> None:
    column = LearningItemKeyPoint.__table__.c.learning_item_id

    assert column.nullable is False
    assert _only_foreign_key(column).ondelete == "CASCADE"


def test_user_session_parent_reference_cascades() -> None:
    column = UserSession.__table__.c.user_id

    assert column.nullable is False
    assert _only_foreign_key(column).ondelete == "CASCADE"


def test_refresh_session_security_columns_are_required_and_bounded() -> None:
    columns = UserSession.__table__.c

    assert columns.token_hash.nullable is False
    assert columns.token_hash.type.length == 64
    assert columns.family_id.nullable is False
    assert columns.expires_at.nullable is False
    assert columns.absolute_expires_at.nullable is False
    assert columns.revoked_at.nullable is True
