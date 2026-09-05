from argparse import Namespace
from copy import deepcopy
from pathlib import Path

import pytest

import scripts.inspect_development_database as inspection
import scripts.upgrade_adoption_rehearsal as adoption_runner
from scripts.inspect_development_database import BASELINE_COLUMNS
from scripts.reconcile_legacy_schema_to_0001 import EXPECTED_LEGACY_TABLES
from scripts.upgrade_adoption_rehearsal import (
    ALEMBIC_ACTION,
    ORDERED_UPGRADE_REVISIONS,
    PREDECESSOR,
    REVISION_0001,
    AdoptionFailure,
    build_alembic_config,
    print_failure,
    retained_legacy_snapshot,
    validate_mode,
    validate_preservation_snapshot_payload,
    validate_upgrade_transition,
    validated_adoption_target,
)


DIRECT_REHEARSAL_URL = (
    "postgresql+psycopg://rehearsal-user:secret@"
    "ep-revisee-rehearsal.eu-central-1.aws.neon.tech/revisee_rehearsal"
)


def _missing_env_file(tmp_path: Path) -> Path:
    return tmp_path / "does-not-exist.env"


def _valid_snapshot() -> dict[str, object]:
    return {
        "format": 1,
        "target_identity_hash": "a" * 64,
        "tables": {
            table_name: {
                "row_count": 0,
                "id_signature": "d41d8cd98f00b204e9800998ecf8427e",
            }
            for table_name in EXPECTED_LEGACY_TABLES
        },
        "sequences": [
            {
                "sequence": f"{table_name}_id_seq",
                "owner_table": table_name,
                "owner_column": "id",
                "last_value": None,
            }
            for table_name in EXPECTED_LEGACY_TABLES
        ],
    }


def test_runner_never_falls_back_to_normal_or_test_targets(tmp_path: Path) -> None:
    with pytest.raises(AdoptionFailure) as failure:
        validated_adoption_target(
            {
                "DATABASE_URL": "postgresql://normal/normal",
                "TEST_DATABASE_URL": "postgresql://test/test",
                "MIGRATION_TEST_DATABASE_URL": "postgresql://migration/test",
            },
            env_file=_missing_env_file(tmp_path),
        )

    assert failure.value.safe_code == "ADOPTION_REHEARSAL_TARGET_REQUIRED"


def test_runner_rejects_pooled_neon_target(tmp_path: Path) -> None:
    pooled = DIRECT_REHEARSAL_URL.replace(
        "ep-revisee-rehearsal.",
        "ep-revisee-rehearsal-pooler.",
    )
    with pytest.raises(AdoptionFailure) as failure:
        validated_adoption_target(
            {"ADOPTION_REHEARSAL_DATABASE_URL": pooled},
            env_file=_missing_env_file(tmp_path),
        )

    assert failure.value.safe_code == "POOLED_NEON_TARGET_REFUSED"


def test_runner_rejects_normalized_target_collision(tmp_path: Path) -> None:
    collision = (
        "postgresql://other:other@"
        "EP-REVISEE-REHEARSAL.EU-CENTRAL-1.AWS.NEON.TECH:5432/"
        "REVISEE_REHEARSAL"
    )
    with pytest.raises(AdoptionFailure) as failure:
        validated_adoption_target(
            {
                "ADOPTION_REHEARSAL_DATABASE_URL": DIRECT_REHEARSAL_URL,
                "DATABASE_URL": collision,
            },
            env_file=_missing_env_file(tmp_path),
        )

    assert failure.value.safe_code == "TARGET_COLLIDES_WITH_DATABASE_URL"


def test_mutations_require_explicit_confirmation() -> None:
    for stamp_0001, upgrade_to in ((True, None), (False, ORDERED_UPGRADE_REVISIONS[0])):
        with pytest.raises(AdoptionFailure) as failure:
            validate_mode(
                Namespace(
                    preflight=False,
                    stamp_0001=stamp_0001,
                    upgrade_to=upgrade_to,
                    confirm_rehearsal_upgrade=False,
                )
            )
        assert (
            failure.value.safe_code
            == "EXPLICIT_REHEARSAL_UPGRADE_CONFIRMATION_REQUIRED"
        )


def test_read_only_preflight_does_not_require_mutation_confirmation() -> None:
    validate_mode(
        Namespace(
            preflight=True,
            stamp_0001=False,
            upgrade_to=None,
            confirm_rehearsal_upgrade=False,
        )
    )


def test_upgrade_order_accepts_only_the_immediate_successor() -> None:
    assert PREDECESSOR[ORDERED_UPGRADE_REVISIONS[0]] == REVISION_0001
    for target in ORDERED_UPGRADE_REVISIONS:
        validate_upgrade_transition(PREDECESSOR[target], target)

        with pytest.raises(AdoptionFailure) as failure:
            validate_upgrade_transition(None, target)
        assert failure.value.safe_code == "REVISION_ORDER_VIOLATION"


def test_upgrade_order_rejects_unknown_target() -> None:
    with pytest.raises(AdoptionFailure) as failure:
        validate_upgrade_transition(REVISION_0001, "head")

    assert failure.value.safe_code == "UPGRADE_TARGET_NOT_ALLOWED"


def test_reconciliation_snapshot_structure_is_strictly_validated() -> None:
    validate_preservation_snapshot_payload(_valid_snapshot())


def test_preservation_comparison_ignores_only_nonlegacy_sequences() -> None:
    snapshot = _valid_snapshot()
    sequences = snapshot["sequences"]
    assert isinstance(sequences, list)
    sequences.append(
        {
            "sequence": "revision_session_labels_id_seq",
            "owner_table": "revision_session_labels",
            "owner_column": "id",
            "last_value": 9,
        }
    )

    retained = retained_legacy_snapshot(snapshot)

    assert retained["tables"] == snapshot["tables"]
    assert len(retained["sequences"]) == len(EXPECTED_LEGACY_TABLES)
    assert {
        sequence["owner_table"] for sequence in retained["sequences"]
    } == set(EXPECTED_LEGACY_TABLES)


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_table",
        "invalid_count",
        "invalid_signature",
        "missing_sequence",
        "wrong_sequence_owner",
    ),
)
def test_invalid_or_nonreconciliation_snapshot_is_refused(mutation: str) -> None:
    snapshot = deepcopy(_valid_snapshot())
    tables = snapshot["tables"]
    sequences = snapshot["sequences"]
    assert isinstance(tables, dict)
    assert isinstance(sequences, list)
    if mutation == "missing_table":
        tables.pop("media")
    elif mutation == "invalid_count":
        tables["media"]["row_count"] = -1
    elif mutation == "invalid_signature":
        tables["media"]["id_signature"] = "not-md5"
    elif mutation == "missing_sequence":
        sequences.pop()
    else:
        sequences[0]["owner_table"] = "not_a_legacy_table"

    with pytest.raises(AdoptionFailure) as failure:
        validate_preservation_snapshot_payload(snapshot)

    assert failure.value.safe_code == "SNAPSHOT_FILE_STRUCTURE_INVALID"


def test_alembic_config_receives_only_explicit_connection_and_rehearsal_url() -> None:
    connection = object()
    config = build_alembic_config(DIRECT_REHEARSAL_URL, connection)

    assert config.attributes["connection"] is connection
    assert (
        config.attributes["adoption_rehearsal_database_url"]
        == DIRECT_REHEARSAL_URL
    )
    assert config.get_main_option("sqlalchemy.url") is None


def test_adoption_failure_output_is_sanitized(capsys) -> None:
    secret_url = "postgresql://user:top-secret@example.invalid/private"
    print_failure(
        AdoptionFailure(
            ALEMBIC_ACTION,
            "ALEMBIC_ACTION_STATE_UNCERTAIN",
            RuntimeError(secret_url),
        )
    )

    output = capsys.readouterr().out
    assert "FAILURE_STAGE=ALEMBIC_ACTION" in output
    assert "ERROR_CODE=ALEMBIC_ACTION_STATE_UNCERTAIN" in output
    assert "ACTION_STATE=UNCERTAIN_INSPECT_BEFORE_RETRY" in output
    assert "RuntimeError" in output
    assert secret_url not in output
    assert "top-secret" not in output


def test_alembic_environment_skips_settings_for_injected_connection() -> None:
    env_source = (Path(__file__).resolve().parents[2] / "alembic" / "env.py").read_text(
        encoding="utf-8"
    )

    assert 'external_connection = config.attributes.get("connection")' in env_source
    assert "if external_connection is None:" in env_source
    assert "connection=external_connection" in env_source


def test_baseline_comparator_ignores_alembic_bookkeeping_catalog_objects(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        inspection,
        "_constraint_metadata",
        lambda _connection: [
            {
                "kind": "p",
                "table": "alembic_version",
                "columns": ("version_num",),
                "name": "alembic_version_pkc",
            }
        ],
    )
    monkeypatch.setattr(
        inspection,
        "_index_metadata",
        lambda _connection: [
            {
                "table": "alembic_version",
                "columns": ("version_num",),
                "unique": True,
                "predicate": None,
                "name": "alembic_version_pkc",
            }
        ],
    )
    monkeypatch.setattr(inspection, "_enum_metadata", lambda _connection: {})

    structural, naming, blockers = inspection.baseline_schema_comparison(
        object(),
        {"alembic_version"},
        {},
    )

    all_differences = (*structural, *naming, *blockers)
    assert not any("alembic_version" in difference for difference in all_differences)


def test_absent_revision_can_be_stamped_and_pass_postcheck_with_bookkeeping(
    monkeypatch,
) -> None:
    state = {
        "revision": None,
        "tables": set(BASELINE_COLUMNS),
    }
    columns = {
        table_name: {column_name: {} for column_name in expected_columns}
        for table_name, expected_columns in BASELINE_COLUMNS.items()
    }
    compared_table_sets: list[set[str]] = []
    preservation_stages: list[str] = []

    monkeypatch.setattr(
        adoption_runner,
        "_current_revision",
        lambda _connection: state["revision"],
    )
    monkeypatch.setattr(
        adoption_runner,
        "schema_metadata",
        lambda _connection: (state["tables"], columns),
    )

    def compare_baseline(_connection, tables, _columns):
        compared_table_sets.append(set(tables))
        return [], [], []

    monkeypatch.setattr(
        adoption_runner,
        "baseline_schema_comparison",
        compare_baseline,
    )
    monkeypatch.setattr(
        adoption_runner,
        "_assert_preservation_snapshot",
        lambda _connection, _snapshot, _target_hash, *, stage: (
            preservation_stages.append(stage)
        ),
    )

    assert state["revision"] is None
    state["revision"] = REVISION_0001
    state["tables"].add("alembic_version")

    adoption_runner._assert_post_action_state(
        object(),
        REVISION_0001,
        _valid_snapshot(),
        "a" * 64,
    )

    assert compared_table_sets == [set(BASELINE_COLUMNS)]
    assert preservation_stages == [adoption_runner.POST_ACTION]
