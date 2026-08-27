from datetime import datetime, timedelta
from decimal import Decimal


def _registered_user_id(db_session) -> int:
    from src.modules.auth.models import User

    return db_session.query(User.id).filter(User.username == "atul").scalar()


def test_weak_areas_require_authentication(client) -> None:
    assert client.get("/weak-areas").status_code == 401


def test_item_classification_filters_before_pagination_and_conceals_foreign_rows(
    client,
    registered_user,
    db_session,
) -> None:
    from src.modules.auth.models import User
    from src.modules.learning_items.models import LearningItem
    from src.modules.mastery.models import UserLearningItemMastery

    user_id = _registered_user_id(db_session)
    foreign = User(
        username="foreign-weak",
        email="foreign-weak@example.test",
        password_hash="not-used",
    )
    db_session.add(foreign)
    db_session.flush()
    weak = LearningItem(user_id=user_id, title="Weak", description_text="notes")
    weakest = LearningItem(user_id=user_id, title="Weakest", description_text="notes")
    due = LearningItem(user_id=user_id, title="Due", description_text="notes")
    missing = LearningItem(user_id=user_id, title="Missing", description_text="notes")
    foreign_item = LearningItem(
        user_id=foreign.id,
        title="Foreign weak",
        description_text="notes",
    )
    db_session.add_all([weak, weakest, due, missing, foreign_item])
    db_session.flush()
    now = datetime.utcnow()
    db_session.add_all(
        [
            UserLearningItemMastery(
                user_id=user_id,
                learning_item_id=weak.id,
                mastery_score=Decimal("30.00"),
                total_attempts=3,
                correct_attempts=1,
                next_review_at=now - timedelta(days=1),
            ),
            UserLearningItemMastery(
                user_id=user_id,
                learning_item_id=weakest.id,
                mastery_score=Decimal("10.00"),
                total_attempts=5,
                correct_attempts=1,
            ),
            UserLearningItemMastery(
                user_id=user_id,
                learning_item_id=due.id,
                mastery_score=Decimal("80.00"),
                total_attempts=3,
                correct_attempts=3,
                next_review_at=now - timedelta(days=1),
            ),
            UserLearningItemMastery(
                user_id=foreign.id,
                learning_item_id=foreign_item.id,
                mastery_score=Decimal("10.00"),
                total_attempts=10,
                correct_attempts=0,
            ),
        ]
    )
    db_session.commit()

    weak_response = client.get(
        "/weak-areas",
        params={"classification": "DEMONSTRATED_WEAKNESS", "limit": 1},
        headers=registered_user["headers"],
    )
    assert weak_response.status_code == 200
    assert weak_response.json()["pagination"]["total"] == 2
    assert [row["entity_id"] for row in weak_response.json()["items"]] == [
        weakest.id
    ]
    second_page = client.get(
        "/weak-areas",
        params={
            "classification": "DEMONSTRATED_WEAKNESS",
            "limit": 1,
            "offset": 1,
        },
        headers=registered_user["headers"],
    ).json()
    assert second_page["pagination"]["total"] == 2
    assert [row["entity_id"] for row in second_page["items"]] == [weak.id]
    assert second_page["items"][0]["is_due"] is True

    due_response = client.get(
        "/weak-areas",
        params={"classification": "DUE_REVIEW"},
        headers=registered_user["headers"],
    )
    assert [row["entity_id"] for row in due_response.json()["items"]] == [due.id]

    insufficient = client.get(
        "/weak-areas",
        params={"classification": "INSUFFICIENT_EVIDENCE"},
        headers=registered_user["headers"],
    )
    assert [row["entity_id"] for row in insufficient.json()["items"]] == [missing.id]
    assert insufficient.json()["items"][0]["mastery_score"] is None


def test_label_weak_area_uses_owned_label_mastery(
    client,
    registered_user,
    db_session,
) -> None:
    from src.modules.labels.models import Label
    from src.modules.mastery.models import UserLabelMastery

    user_id = _registered_user_id(db_session)
    label = Label(user_id=user_id, label_name="Weak label")
    db_session.add(label)
    db_session.flush()
    db_session.add(
        UserLabelMastery(
            user_id=user_id,
            label_id=label.id,
            mastery_score=Decimal("59.99"),
            total_attempts=3,
            correct_attempts=2,
        )
    )
    db_session.commit()

    response = client.get(
        "/weak-areas",
        params={
            "entity_type": "LABEL",
            "classification": "DEMONSTRATED_WEAKNESS",
        },
        headers=registered_user["headers"],
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["entity_id"] == label.id
    assert response.json()["items"][0]["accuracy_percent"] == 66.67
