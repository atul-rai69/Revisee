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


def test_user_session_active_defaults_preserve_nullable_behavior() -> None:
    column = UserSession.__table__.c.is_active

    assert column.nullable is True
    assert column.default is not None
    assert column.default.arg is True
    assert column.server_default is not None
    assert str(column.server_default.arg).casefold() == "true"
