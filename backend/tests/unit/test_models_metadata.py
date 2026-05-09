from sqlalchemy import CheckConstraint

from app.db.models import Base


def test_core_tables_are_registered() -> None:
    expected_tables = {
        "instances",
        "instance_collect_status",
        "snapshot_frames",
        "session_snapshots",
        "request_snapshots",
        "wait_snapshots",
        "blocking_snapshots",
        "sql_texts",
        "kill_audits",
        "users",
    }

    assert expected_tables <= set(Base.metadata.tables)


def test_required_check_constraints_are_registered() -> None:
    expected_constraints = {
        "instances": {"instances_status_check"},
        "kill_audits": {"kill_audits_result_check"},
        "users": {"users_role_check", "users_status_check"},
    }

    for table_name, constraint_names in expected_constraints.items():
        table = Base.metadata.tables[table_name]
        actual_names = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }

        assert constraint_names <= actual_names


def test_required_indexes_are_registered() -> None:
    expected_indexes = {
        "snapshot_frames": {"idx_snapshot_frames_instance_time"},
        "session_snapshots": {
            "idx_session_snapshots_instance_time",
            "idx_session_snapshots_session_time",
            "idx_session_snapshots_open_tran",
        },
        "request_snapshots": {
            "idx_request_snapshots_instance_time",
            "idx_request_snapshots_cpu",
            "idx_request_snapshots_io",
            "idx_request_snapshots_blocking",
        },
        "wait_snapshots": {"idx_wait_snapshots_instance_time"},
        "blocking_snapshots": {"idx_blocking_snapshots_instance_time"},
        "sql_texts": {"idx_sql_texts_normalized_hash"},
    }

    for table_name, index_names in expected_indexes.items():
        table = Base.metadata.tables[table_name]
        actual_names = {index.name for index in table.indexes}

        assert index_names <= actual_names


def test_snapshot_tables_include_frame_id() -> None:
    snapshot_tables = {
        "session_snapshots",
        "request_snapshots",
        "wait_snapshots",
        "blocking_snapshots",
    }

    for table_name in snapshot_tables:
        table = Base.metadata.tables[table_name]

        assert "frame_id" in table.columns
