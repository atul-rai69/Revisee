from datetime import date

from src.modules.mastery import repository
from src.modules.mastery.repository import RevisionActivityRow, TopicPracticeRow
from src.modules.mastery.service import RevisionAnalyticsService


class FakeDb:
    def __init__(self) -> None:
        self.rollbacks = 0

    def rollback(self) -> None:
        self.rollbacks += 1


def test_revision_activity_uses_weighted_answer_accuracy(monkeypatch) -> None:
    db = FakeDb()
    monkeypatch.setattr(
        repository,
        "list_owned_revision_activity",
        lambda *_args, **_kwargs: (
            [RevisionActivityRow(date(2026, 9, 14), 2, 10, 7)],
            2,
        ),
    )
    monkeypatch.setattr(
        repository,
        "list_owned_topic_practice",
        lambda *_args, **_kwargs: ([], 2),
    )
    monkeypatch.setattr(
        repository,
        "count_owned_measured_learning_items",
        lambda *_args, **_kwargs: 0,
    )

    response = RevisionAnalyticsService(db).get(9, 7)

    assert response.activity[0].accuracy_percent == 70
    assert response.activity[0].answered_count == 10
    assert response.requested_session_limit == 7
    assert response.sessions_used == 2
    assert response.weak_area_ready is False
    assert db.rollbacks == 1


def test_topic_distribution_keeps_overlapping_topic_totals(monkeypatch) -> None:
    db = FakeDb()
    monkeypatch.setattr(
        repository,
        "list_owned_revision_activity",
        lambda *_args, **_kwargs: ([], 4),
    )
    monkeypatch.setattr(
        repository,
        "list_owned_topic_practice",
        lambda *_args, **_kwargs: (
            [
                TopicPracticeRow(1, "Databases", 5, 4, 3),
                TopicPracticeRow(2, "Programming", 5, 4, 3),
            ],
            4,
        ),
    )
    monkeypatch.setattr(
        repository,
        "count_owned_measured_learning_items",
        lambda *_args, **_kwargs: 1,
    )

    response = RevisionAnalyticsService(db).get(3, 50)

    assert [point.attempt_count for point in response.topic_practice] == [5, 5]
    assert all(point.accuracy_percent == 80 for point in response.topic_practice)
    assert response.sessions_used == 4
    assert response.weak_area_ready is True
    assert "totals can overlap" in response.attribution_note
