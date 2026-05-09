from __future__ import annotations

SESSION_REQUEST_SQL = """
SELECT
    s.session_id,
    s.login_name,
    s.host_name,
    s.program_name,
    DB_NAME(COALESCE(r.database_id, s.database_id)) AS database_name,
    s.status AS session_status,
    s.open_transaction_count,
    s.login_time,
    s.last_request_start_time,
    s.last_request_end_time,
    s.cpu_time AS session_cpu_time,
    s.reads AS session_reads,
    s.writes AS session_writes,
    s.logical_reads AS session_logical_reads,
    r.request_id,
    r.status AS request_status,
    r.command,
    r.start_time,
    r.cpu_time AS request_cpu_time_ms,
    r.total_elapsed_time AS total_elapsed_time_ms,
    r.reads AS request_reads,
    r.writes AS request_writes,
    r.logical_reads AS request_logical_reads,
    r.row_count,
    r.wait_type,
    r.wait_time AS wait_time_ms,
    r.blocking_session_id,
    r.percent_complete,
    r.sql_handle,
    r.plan_handle,
    r.statement_start_offset,
    r.statement_end_offset,
    t.text AS sql_text
FROM sys.dm_exec_sessions s
LEFT JOIN sys.dm_exec_requests r
    ON s.session_id = r.session_id
OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) t
WHERE s.is_user_process = 1;
""".strip()
