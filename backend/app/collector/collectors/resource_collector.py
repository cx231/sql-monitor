from __future__ import annotations

RESOURCE_SQL = """
WITH cpu_sample AS (
    SELECT TOP (1)
        SQLProcessUtilization,
        SystemIdle
    FROM (
        SELECT
            record.value('(./Record/SchedulerMonitorEvent/SystemHealth/ProcessUtilization)[1]', 'int')
                AS SQLProcessUtilization,
            record.value('(./Record/SchedulerMonitorEvent/SystemHealth/SystemIdle)[1]', 'int')
                AS SystemIdle,
            [timestamp]
        FROM (
            SELECT
                [timestamp],
                CONVERT(xml, record) AS record
            FROM sys.dm_os_ring_buffers
            WHERE ring_buffer_type = N'RING_BUFFER_SCHEDULER_MONITOR'
              AND record LIKE '%<SystemHealth>%'
        ) AS ring_buffer
    ) AS cpu_records
    ORDER BY [timestamp] DESC
),
memory_sample AS (
    SELECT
        CAST(
            CASE
                WHEN total_physical_memory_kb > 0
                    THEN (total_physical_memory_kb - available_physical_memory_kb) * 100.0
                        / total_physical_memory_kb
                ELSE NULL
            END
            AS decimal(9, 2)
        ) AS memory_usage_percent
    FROM sys.dm_os_sys_memory
),
network_sample AS (
    SELECT
        SUM(num_writes * CAST(net_packet_size AS bigint)) AS network_bytes_sent_total,
        SUM(num_reads * CAST(net_packet_size AS bigint)) AS network_bytes_received_total
    FROM sys.dm_exec_connections
)
SELECT
    CAST(
        CASE
            WHEN cpu_sample.SystemIdle IS NOT NULL
                THEN 100 - cpu_sample.SystemIdle
            WHEN cpu_sample.SQLProcessUtilization IS NOT NULL
                THEN cpu_sample.SQLProcessUtilization
            ELSE NULL
        END
        AS decimal(9, 2)
    ) AS cpu_load_percent,
    memory_sample.memory_usage_percent,
    network_sample.network_bytes_sent_total,
    network_sample.network_bytes_received_total
FROM cpu_sample
CROSS JOIN memory_sample
CROSS JOIN network_sample;
""".strip()
