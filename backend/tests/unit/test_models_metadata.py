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
        "sql_texts": {"idx_sql_texts_normalized_hash"},
    }

    for table_name, index_names in expected_indexes.items():
        table = Base.metadata.tables[table_name]
        actual_names = {index.name for index in table.indexes}

        assert index_names <= actual_names
