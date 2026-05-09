# SQL Server 实时会话监控平台技术设计

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档类型 | 技术设计 |
| 关联 PRD | `docs/sql-server-realtime-session-monitor-prd.md` |
| 方案状态 | 待确认 |
| 技术栈 | Vue 3 + FastAPI + PostgreSQL + pyodbc |
| 部署方式 | 内网 Linux 服务器直接部署 |
| 当前目标 | 补齐进入开发前所需的工程设计 |

## 2. 设计目标

本技术设计用于把 PRD 中的产品需求转化为可开发、可测试、可部署的工程方案。

核心目标：

1. 明确前端、后端、Collector、PostgreSQL 的职责边界。
2. 明确 SQL Server DMV 和 Extended Events 采集方案。
3. 明确 PostgreSQL 表结构、索引、分区和保留策略。
4. 明确 API 请求、响应、分页、排序、筛选和错误格式。
5. 明确 Kill Session 的权限、安全校验和审计流程。
6. 明确直接部署所需配置、服务和运行要求。
7. 明确 MVP 阶段的测试和验收口径。

## 2.1 与 PRD 的范围差异

PRD 的 MVP 总体验收标准包含“捕获并查看死锁事件”。本技术设计建议将 Deadlock 捕获放入 P1，原因是首版 P0 的关键闭环是 Session、SQL、Wait、Blocking、Kill 和历史回放；Deadlock 依赖 Extended Events 权限、XML 解析和去重逻辑，适合在基础采集链路稳定后实现。

该差异需要在方案评审时确认：

1. 如果 Deadlock 必须进入 P0，则需要把 `deadlock_collector`、`deadlock_events`、死锁列表和详情页纳入首轮开发。
2. 如果接受本技术设计建议，则 P0 只预留 deadlock 表、路由和页面入口，实际捕获能力在 P1 实现。

## 3. 架构决策

## 3.1 推荐方案

采用以下架构：

```text
Vue Frontend
  |
  | HTTP polling
  v
Nginx
  |
  | /api
  v
FastAPI API Service
  |
  | SQLAlchemy async
  v
PostgreSQL

Python Collector Service
  |
  | pyodbc
  v
SQL Server Instances

Python Collector Service
  |
  | batch insert
  v
PostgreSQL
```

## 3.2 关键取舍

### 方案 A：API 与 Collector 同进程

优点：

1. 开发简单。
2. 部署服务少。
3. 适合很小规模原型。

缺点：

1. Collector 阻塞或异常会影响 API。
2. 调度、连接池、请求处理互相干扰。
3. 后续扩展多实例采集困难。

### 方案 B：API 与 Collector 独立进程

优点：

1. API 和采集互相隔离。
2. Collector 异常不拖垮页面查询。
3. 便于后续扩展多个 Collector。
4. 符合直接部署和 systemd 管理方式。

缺点：

1. 多一个服务进程。
2. 需要设计进程健康检查和日志。

### 方案 C：消息队列异步采集

优点：

1. 解耦程度高。
2. 适合大规模实例和高吞吐。

缺点：

1. MVP 复杂度过高。
2. 需要额外部署 Redis、RabbitMQ 或 Kafka。
3. 增加运维成本。

### 结论

MVP 采用 **方案 B：API 与 Collector 独立进程**。

首版不引入消息队列，不使用 WebSocket。前端使用 HTTP 轮询，后端从 PostgreSQL 读取最新快照。

## 4. 系统边界

## 4.1 API Service 职责

1. 用户认证和权限校验。
2. 实例管理。
3. Dashboard 查询。
4. Session、SQL、Blocking、Wait、TempDB、Deadlock 查询。
5. 历史回放查询。
6. Kill Session 操作。
7. 审计查询。
8. 系统配置查询。

API Service 不直接执行周期性采集任务。

## 4.2 Collector Service 职责

1. 加载启用状态的 SQL Server 实例。
2. 按实例独立调度采集任务。
3. 执行 DMV 采集 SQL。
4. 解析阻塞链。
5. 采集 TempDB 和 Wait 数据。
6. 读取 deadlock 事件。
7. 写入 PostgreSQL 快照表。
8. 更新实例采集状态。
9. 清理过期历史数据。

Collector 不提供 HTTP API。

## 4.3 PostgreSQL 职责

1. 存储实例配置。
2. 存储最新和历史快照。
3. 存储 SQL 文本和 SQL 指纹。
4. 存储死锁事件。
5. 存储 Kill 审计。
6. 存储用户、角色和配置。

## 4.4 前端职责

1. 展示实时监控页面。
2. 管理刷新间隔和暂停刷新。
3. 展示表格、图表、详情抽屉。
4. 执行筛选、排序、分页请求。
5. 发起 Kill 操作并展示确认弹窗。

前端不保存业务状态，刷新后从 API 重新获取数据。

## 5. 运行时流程

## 5.1 实时数据流程

```text
Collector timer
  -> load enabled instances
  -> connect SQL Server
  -> collect sessions / requests / waits / blocking / tempdb
  -> normalize sql text and hashes
  -> calculate blocking chain
  -> batch insert PostgreSQL snapshot tables
  -> update instance_collect_status
  -> frontend polls API
  -> API reads latest snapshot
  -> frontend renders data
```

## 5.2 历史回放流程

```text
User selects instance and time
  -> frontend calls /api/replay
  -> API finds nearest snapshot_time
  -> API loads session/request/blocking/wait/tempdb snapshots
  -> API returns a replay frame
  -> frontend renders historical dashboard and tables
```

历史回放默认使用“最接近且不晚于目标时间”的快照。允许配置最大容忍偏差，默认 10 秒。

## 5.3 Kill Session 流程

```text
User clicks Kill
  -> frontend loads latest session detail
  -> frontend shows confirmation modal
  -> user enters reason
  -> API checks user role
  -> API checks target session safety rules
  -> API opens SQL Server kill connection
  -> API records before_snapshot
  -> API executes KILL <session_id>
  -> API writes kill_audits
  -> API returns result
  -> frontend refreshes blocking/session data
```

Kill 操作不通过 Collector 执行，避免定时采集任务拥有处置权限。

## 6. 后端设计

## 6.1 目录结构

建议结构：

```text
backend/
  app/
    main.py
    config.py
    logging.py
    db/
      postgres.py
      migrations/
    api/
      deps.py
      routes/
        auth.py
        instances.py
        dashboard.py
        sessions.py
        sqls.py
        blocking.py
        waits.py
        resources.py
        tempdb.py
        deadlocks.py
        replay.py
        kill.py
        audits.py
    models/
    schemas/
    services/
      instance_service.py
      dashboard_service.py
      session_service.py
      blocking_service.py
      replay_service.py
      kill_service.py
      auth_service.py
    collector/
      main.py
      scheduler.py
      instance_runner.py
      sqlserver_client.py
      sql_text.py
      blocking_graph.py
      retention.py
      collectors/
        session_request_collector.py
        wait_collector.py
        tempdb_collector.py
        deadlock_collector.py
```

## 6.2 Python 运行方式

API：

```text
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Collector：

```text
python -m app.collector.main
```

## 6.3 依赖建议

| 用途 | 依赖 |
|---|---|
| Web 框架 | fastapi |
| ASGI Server | uvicorn |
| PostgreSQL ORM | sqlalchemy |
| PostgreSQL Driver | asyncpg |
| SQL Server Driver | pyodbc |
| 迁移 | alembic |
| 配置 | pydantic-settings |
| 定时任务 | apscheduler |
| 密码哈希 | passlib 或 bcrypt |
| JWT | python-jose 或 PyJWT |
| 测试 | pytest |
| HTTP 测试 | httpx |

## 7. Collector 设计

## 7.1 调度模型

MVP 使用单 Collector 进程。每个实例一个独立采集循环。

默认频率：

| 采集项 | 频率 |
|---|---|
| Session / Request | 5 秒 |
| Wait | 5 秒 |
| Blocking | 5 秒 |
| TempDB | 10 秒 |
| Deadlock | 10 秒 |
| Instance health | 10 秒 |
| Retention cleanup | 1 小时 |

同一实例同一采集项不允许并发重入。如果上一次采集未完成，跳过本轮并记录 `skipped_overlap`。

## 7.2 实例隔离

每个实例的采集必须独立：

1. 独立连接。
2. 独立超时。
3. 独立错误计数。
4. 独立状态更新。
5. 单实例失败不影响其他实例。

采集状态写入 `instance_collect_status`。

## 7.3 超时策略

| 操作 | 超时 |
|---|---|
| SQL Server 连接 | 5 秒 |
| DMV 查询 | 3 秒 |
| Deadlock 读取 | 5 秒 |
| PostgreSQL 写入 | 5 秒 |

连续失败 3 次后，实例状态置为 `collect_error`。下一轮仍继续尝试恢复。

## 7.4 SQL 文本处理

SQL 文本处理步骤：

1. 获取原始 SQL text。
2. 截取当前 statement 范围。
3. 生成 `sql_hash`。
4. 简单归一化生成 `normalized_hash`。
5. 写入 `sql_texts`。
6. 快照表只保存 hash。

MVP 归一化规则：

1. 去除首尾空白。
2. 连续空白合并为一个空格。
3. 转为小写。
4. 将数字字面量替换为 `?`。
5. 将单引号字符串替换为 `?`。

说明：MVP 不做完整 SQL parser 级归一化。

## 7.5 阻塞链计算

输入：

1. `request_snapshots.session_id`
2. `request_snapshots.blocking_session_id`
3. `wait_snapshots.resource_description`
4. `session_snapshots.open_transaction_count`

算法：

1. 构建有向边：`blocking_session_id -> blocked_session_id`。
2. 过滤 `blocking_session_id` 为 `0` 或 `NULL` 的请求。
3. 对每个被阻塞节点向上寻找根节点。
4. 根节点定义为：阻塞别人，且自身不被其他 session 阻塞。
5. 对异常 blocker 进行特殊标记：
   - `-2`：孤立分布式事务。
   - `-3`：延迟恢复事务。
   - `-4`：内部锁状态转换导致无法确定。
6. 检测环形关系，发现环时标记 `cycle_detected=true`，避免无限遍历。
7. 生成 `blocking_snapshots`。

输出字段：

1. `root_session_id`
2. `blocking_session_id`
3. `blocked_session_id`
4. `chain_depth`
5. `blocked_count`
6. `max_wait_time_ms`
7. `resource_description`

## 7.6 死锁采集

MVP 优先读取 SQL Server 默认 `system_health` Extended Events 中的 `xml_deadlock_report`。

采集方式：

1. 查询 `system_health` ring buffer。
2. 解析 `xml_deadlock_report`。
3. 提取 victim、process、resource、SQL inputbuf。
4. 使用 deadlock XML hash 去重。
5. 写入 `deadlock_events`。

如果 ring buffer 不可用，再支持读取 event file target。

限制：

1. ring buffer 容量有限，极端情况下可能丢失历史死锁。
2. MVP 不主动创建新的 Extended Events session。
3. 如果权限不足，实例详情中展示 `deadlock_collect_unsupported`。

## 8. SQL Server 采集 SQL

## 8.1 Session / Request 采集

用途：生成 `session_snapshots`、`request_snapshots` 和 `sql_texts`。

```sql
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
```

## 8.2 Wait 采集

用途：生成当前等待明细和聚合数据。

```sql
SELECT
    wt.session_id,
    wt.exec_context_id,
    wt.wait_duration_ms,
    wt.wait_type,
    wt.blocking_session_id,
    wt.resource_description
FROM sys.dm_os_waiting_tasks wt
WHERE wt.session_id IS NOT NULL;
```

聚合由 Collector 或 PostgreSQL 侧完成：

```text
GROUP BY wait_type
COUNT(*) AS waiting_tasks_count
SUM(wait_duration_ms) AS total_wait_time_ms
MAX(wait_duration_ms) AS max_wait_time_ms
```

## 8.3 锁信息采集

用途：Session 详情和阻塞链详情。

```sql
SELECT
    l.request_session_id AS session_id,
    l.resource_type,
    l.resource_database_id,
    DB_NAME(l.resource_database_id) AS database_name,
    l.resource_associated_entity_id,
    l.request_mode,
    l.request_status,
    l.request_owner_type
FROM sys.dm_tran_locks l
WHERE l.request_session_id IS NOT NULL;
```

MVP 锁信息不做全量历史存储。默认只在 Session 详情按需查询，阻塞快照只保存 `resource_description`。

## 8.4 事务信息采集

用途：识别 sleeping 未提交事务和长事务。

```sql
SELECT
    st.session_id,
    at.transaction_id,
    at.name AS transaction_name,
    at.transaction_begin_time,
    at.transaction_type,
    at.transaction_state,
    dt.database_id,
    DB_NAME(dt.database_id) AS database_name
FROM sys.dm_tran_session_transactions st
JOIN sys.dm_tran_active_transactions at
    ON st.transaction_id = at.transaction_id
LEFT JOIN sys.dm_tran_database_transactions dt
    ON st.transaction_id = dt.transaction_id;
```

## 8.5 TempDB 采集

用途：生成 `tempdb_snapshots`。

```sql
SELECT
    ssu.session_id,
    ssu.user_objects_alloc_page_count,
    ssu.user_objects_dealloc_page_count,
    ssu.internal_objects_alloc_page_count,
    ssu.internal_objects_dealloc_page_count,
    (
        (ssu.user_objects_alloc_page_count - ssu.user_objects_dealloc_page_count)
        + (ssu.internal_objects_alloc_page_count - ssu.internal_objects_dealloc_page_count)
    ) * 8.0 / 1024 AS tempdb_current_mb
FROM sys.dm_db_session_space_usage ssu
WHERE ssu.session_id > 50;
```

任务级 TempDB 使用可以补充：

```sql
SELECT
    tsu.session_id,
    tsu.request_id,
    tsu.user_objects_alloc_page_count,
    tsu.user_objects_dealloc_page_count,
    tsu.internal_objects_alloc_page_count,
    tsu.internal_objects_dealloc_page_count
FROM sys.dm_db_task_space_usage tsu
WHERE tsu.session_id > 50;
```

## 8.6 文件 IO 采集

P1 可实现。MVP 不作为阻塞项。

```sql
SELECT
    DB_NAME(vfs.database_id) AS database_name,
    mf.physical_name,
    vfs.num_of_reads,
    vfs.num_of_writes,
    vfs.io_stall_read_ms,
    vfs.io_stall_write_ms,
    vfs.size_on_disk_bytes
FROM sys.dm_io_virtual_file_stats(NULL, NULL) vfs
JOIN sys.master_files mf
    ON vfs.database_id = mf.database_id
   AND vfs.file_id = mf.file_id;
```

## 8.7 Query Plan 获取

查询计划按需获取，不参与 5 秒定时采集。

```sql
SELECT query_plan
FROM sys.dm_exec_query_plan(?);
```

API 在 SQL 详情中通过 `plan_handle` 查询。若返回空，前端展示“查询计划已不可用或无权限”。

## 8.8 Deadlock 采集

读取 `system_health` ring buffer：

```sql
SELECT
    CAST(xet.target_data AS XML) AS target_data
FROM sys.dm_xe_session_targets xet
JOIN sys.dm_xe_sessions xe
    ON xe.address = xet.event_session_address
WHERE xe.name = 'system_health'
  AND xet.target_name = 'ring_buffer';
```

Collector 在 XML 中筛选 `xml_deadlock_report`。

## 9. SQL Server 权限

## 9.1 采集账号权限

SQL Server 2019 及更早版本：

```sql
GRANT VIEW SERVER STATE TO [sqlmon_collect];
```

SQL Server 2022 及更新版本：

```sql
GRANT VIEW SERVER PERFORMANCE STATE TO [sqlmon_collect];
```

说明：

1. `sys.dm_exec_sessions` 查看全量会话需要服务器级状态权限。
2. `sys.dm_exec_requests` 在 SQL Server 2022 及以后需要 `VIEW SERVER PERFORMANCE STATE`。
3. `sys.dm_os_waiting_tasks` 在 SQL Server 2022 及以后需要 `VIEW SERVER PERFORMANCE STATE`。

## 9.2 Kill 账号权限

Kill 账号单独配置，不与采集账号共用。

SQL Server：

```sql
GRANT ALTER ANY CONNECTION TO [sqlmon_kill];
```

如果企业安全要求更高，可以不配置 Kill 账号，平台仅展示 Kill 建议，由 DBA 登录 SSMS 手动执行。

## 9.3 权限检测

实例连接测试时执行权限检测：

1. 能否连接实例。
2. 能否读取 `sys.dm_exec_sessions`。
3. 能否读取 `sys.dm_exec_requests`。
4. 能否读取 `sys.dm_os_waiting_tasks`。
5. 能否读取 `system_health`。
6. Kill 账号是否具备 Kill 权限。

检测结果写入 `instance_capabilities`。

## 10. PostgreSQL 数据库设计

## 10.1 设计原则

1. 配置表使用普通表。
2. 快照表按 `snapshot_time` 日分区。
3. 所有快照表必须包含 `instance_id` 和 `snapshot_time`。
4. 最新实时查询只读取最近一个 snapshot frame。
5. 历史回放按实例和时间查分区。
6. SQL 文本去重存储，快照表只存 hash。
7. 大字段 JSON/XML 单独存储，避免污染实时查询。

## 10.2 核心 DDL

### 10.2.1 instances

```sql
CREATE TABLE instances (
    id uuid PRIMARY KEY,
    name varchar(128) NOT NULL,
    host varchar(255) NOT NULL,
    port integer NOT NULL DEFAULT 1433,
    database_name varchar(128),
    environment varchar(32) NOT NULL DEFAULT 'prod',
    encrypted_collect_dsn text NOT NULL,
    encrypted_kill_dsn text,
    status varchar(32) NOT NULL DEFAULT 'disabled',
    collect_interval_seconds integer NOT NULL DEFAULT 5,
    retention_days integer NOT NULL DEFAULT 7,
    business_owner varchar(128),
    dba_owner varchar(128),
    sqlserver_version varchar(128),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT instances_status_check
        CHECK (status IN ('online', 'offline', 'collect_error', 'disabled'))
);
```

### 10.2.2 instance_collect_status

```sql
CREATE TABLE instance_collect_status (
    instance_id uuid PRIMARY KEY REFERENCES instances(id),
    last_success_at timestamptz,
    last_failure_at timestamptz,
    last_duration_ms integer,
    consecutive_failures integer NOT NULL DEFAULT 0,
    status varchar(32) NOT NULL DEFAULT 'unknown',
    error_code varchar(64),
    error_message text,
    capabilities jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

### 10.2.3 snapshot_frames

每轮采集生成一个 frame，用于把多个快照表对齐到同一时刻。

```sql
CREATE TABLE snapshot_frames (
    id uuid NOT NULL,
    instance_id uuid NOT NULL REFERENCES instances(id),
    snapshot_time timestamptz NOT NULL,
    collect_duration_ms integer NOT NULL,
    status varchar(32) NOT NULL,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, snapshot_time)
) PARTITION BY RANGE (snapshot_time);
```

### 10.2.4 session_snapshots

```sql
CREATE TABLE session_snapshots (
    id uuid NOT NULL,
    frame_id uuid NOT NULL,
    instance_id uuid NOT NULL REFERENCES instances(id),
    snapshot_time timestamptz NOT NULL,
    session_id integer NOT NULL,
    login_name varchar(256),
    host_name varchar(256),
    program_name varchar(512),
    database_name varchar(128),
    status varchar(64),
    open_transaction_count integer NOT NULL DEFAULT 0,
    login_time timestamptz,
    last_request_start_time timestamptz,
    last_request_end_time timestamptz,
    cpu_time bigint,
    reads bigint,
    writes bigint,
    logical_reads bigint,
    current_sql_hash varchar(64),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, snapshot_time)
) PARTITION BY RANGE (snapshot_time);
```

索引：

```sql
CREATE INDEX idx_session_snapshots_instance_time
    ON session_snapshots (instance_id, snapshot_time DESC);

CREATE INDEX idx_session_snapshots_session_time
    ON session_snapshots (instance_id, session_id, snapshot_time DESC);

CREATE INDEX idx_session_snapshots_open_tran
    ON session_snapshots (instance_id, snapshot_time DESC, open_transaction_count);
```

### 10.2.5 request_snapshots

```sql
CREATE TABLE request_snapshots (
    id uuid NOT NULL,
    frame_id uuid NOT NULL,
    instance_id uuid NOT NULL REFERENCES instances(id),
    snapshot_time timestamptz NOT NULL,
    session_id integer NOT NULL,
    request_id integer,
    database_name varchar(128),
    status varchar(64),
    command varchar(128),
    start_time timestamptz,
    duration_ms bigint,
    cpu_time_ms bigint,
    total_elapsed_time_ms bigint,
    reads bigint,
    writes bigint,
    logical_reads bigint,
    row_count bigint,
    wait_type varchar(128),
    wait_time_ms bigint,
    blocking_session_id integer,
    percent_complete numeric(5,2),
    sql_hash varchar(64),
    normalized_sql_hash varchar(64),
    plan_handle bytea,
    statement_start_offset integer,
    statement_end_offset integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, snapshot_time)
) PARTITION BY RANGE (snapshot_time);
```

索引：

```sql
CREATE INDEX idx_request_snapshots_instance_time
    ON request_snapshots (instance_id, snapshot_time DESC);

CREATE INDEX idx_request_snapshots_cpu
    ON request_snapshots (instance_id, snapshot_time DESC, cpu_time_ms DESC);

CREATE INDEX idx_request_snapshots_io
    ON request_snapshots (instance_id, snapshot_time DESC, logical_reads DESC);

CREATE INDEX idx_request_snapshots_blocking
    ON request_snapshots (instance_id, snapshot_time DESC, blocking_session_id);
```

### 10.2.6 wait_snapshots

```sql
CREATE TABLE wait_snapshots (
    id uuid NOT NULL,
    frame_id uuid NOT NULL,
    instance_id uuid NOT NULL REFERENCES instances(id),
    snapshot_time timestamptz NOT NULL,
    wait_type varchar(128) NOT NULL,
    wait_category varchar(64) NOT NULL,
    waiting_tasks_count integer NOT NULL,
    total_wait_time_ms bigint NOT NULL,
    max_wait_time_ms bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, snapshot_time)
) PARTITION BY RANGE (snapshot_time);
```

### 10.2.7 blocking_snapshots

```sql
CREATE TABLE blocking_snapshots (
    id uuid NOT NULL,
    frame_id uuid NOT NULL,
    instance_id uuid NOT NULL REFERENCES instances(id),
    snapshot_time timestamptz NOT NULL,
    root_session_id integer,
    blocking_session_id integer,
    blocked_session_id integer NOT NULL,
    chain_depth integer NOT NULL,
    blocked_count integer NOT NULL DEFAULT 0,
    max_wait_time_ms bigint,
    wait_type varchar(128),
    resource_description text,
    cycle_detected boolean NOT NULL DEFAULT false,
    special_blocker_code integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, snapshot_time)
) PARTITION BY RANGE (snapshot_time);
```

### 10.2.8 tempdb_snapshots

```sql
CREATE TABLE tempdb_snapshots (
    id uuid NOT NULL,
    frame_id uuid NOT NULL,
    instance_id uuid NOT NULL REFERENCES instances(id),
    snapshot_time timestamptz NOT NULL,
    session_id integer NOT NULL,
    request_id integer,
    user_objects_alloc_page_count bigint,
    user_objects_dealloc_page_count bigint,
    internal_objects_alloc_page_count bigint,
    internal_objects_dealloc_page_count bigint,
    tempdb_current_mb numeric(18,2),
    sql_hash varchar(64),
    wait_type varchar(128),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, snapshot_time)
) PARTITION BY RANGE (snapshot_time);
```

### 10.2.9 sql_texts

```sql
CREATE TABLE sql_texts (
    sql_hash varchar(64) PRIMARY KEY,
    normalized_sql_hash varchar(64),
    sql_text text NOT NULL,
    sql_preview varchar(512),
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL
);

CREATE INDEX idx_sql_texts_normalized_hash
    ON sql_texts (normalized_sql_hash);
```

### 10.2.10 deadlock_events

```sql
CREATE TABLE deadlock_events (
    id uuid PRIMARY KEY,
    instance_id uuid NOT NULL REFERENCES instances(id),
    occurred_at timestamptz NOT NULL,
    deadlock_hash varchar(64) NOT NULL,
    victim_session_id integer,
    database_name varchar(128),
    deadlock_xml text NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (instance_id, deadlock_hash)
);

CREATE INDEX idx_deadlock_events_instance_time
    ON deadlock_events (instance_id, occurred_at DESC);
```

### 10.2.11 kill_audits

```sql
CREATE TABLE kill_audits (
    id uuid PRIMARY KEY,
    operator_user_id uuid,
    operator_name varchar(128) NOT NULL,
    instance_id uuid NOT NULL REFERENCES instances(id),
    session_id integer NOT NULL,
    reason text NOT NULL,
    before_snapshot jsonb NOT NULL,
    result varchar(32) NOT NULL,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT kill_audits_result_check
        CHECK (result IN ('success', 'failed', 'rejected'))
);
```

### 10.2.12 users / roles

MVP 使用本地账号。

```sql
CREATE TABLE users (
    id uuid PRIMARY KEY,
    username varchar(128) NOT NULL UNIQUE,
    password_hash text NOT NULL,
    display_name varchar(128),
    role varchar(32) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_role_check
        CHECK (role IN ('viewer', 'developer', 'dba', 'admin')),
    CONSTRAINT users_status_check
        CHECK (status IN ('active', 'disabled'))
);
```

## 10.3 分区策略

所有快照表按天创建分区。

示例：

```sql
CREATE TABLE session_snapshots_20260509
    PARTITION OF session_snapshots
    FOR VALUES FROM ('2026-05-09 00:00:00+08')
             TO ('2026-05-10 00:00:00+08');
```

Collector 每天提前创建未来 2 天分区。

## 10.4 保留策略

默认保留：

| 数据 | 保留时间 |
|---|---|
| session/request/blocking/wait/tempdb snapshots | 7 天 |
| sql_texts | 7 天，若仍被未过期快照引用则保留 |
| deadlock_events | 30 天 |
| kill_audits | 180 天 |

清理策略：

1. 快照表按分区 drop。
2. deadlock 和 audit 按时间 delete。
3. SQL 文本通过引用检查清理。

## 11. API 设计

## 11.1 通用约定

### 时间格式

所有 API 时间字段使用 ISO 8601，带时区。

示例：

```json
"2026-05-09T10:30:00+08:00"
```

### 分页参数

```text
page=1
page_size=50
```

限制：

1. `page_size` 默认 50。
2. `page_size` 最大 500。

### 排序参数

```text
sort_by=cpu_time_ms
sort_order=desc
```

后端只允许白名单字段排序。

### 响应 envelope

成功：

```json
{
  "success": true,
  "data": {},
  "request_id": "req_..."
}
```

失败：

```json
{
  "success": false,
  "error": {
    "code": "INSTANCE_CONNECT_FAILED",
    "message": "Failed to connect SQL Server instance",
    "details": {}
  },
  "request_id": "req_..."
}
```

## 11.2 错误码

| 错误码 | HTTP | 说明 |
|---|---:|---|
| UNAUTHORIZED | 401 | 未登录 |
| FORBIDDEN | 403 | 无权限 |
| INSTANCE_NOT_FOUND | 404 | 实例不存在 |
| INSTANCE_CONNECT_FAILED | 400 | 实例连接失败 |
| COLLECT_DATA_STALE | 409 | 数据已过期 |
| SESSION_NOT_FOUND | 404 | Session 不存在 |
| KILL_REJECTED | 400 | Kill 安全校验拒绝 |
| KILL_FAILED | 500 | Kill 执行失败 |
| VALIDATION_ERROR | 422 | 参数错误 |

## 11.3 核心 API

### 11.3.1 实例列表

```text
GET /api/instances
```

响应：

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "prod-sql-01",
      "host": "10.0.0.10",
      "port": 1433,
      "environment": "prod",
      "status": "online",
      "last_success_at": "2026-05-09T10:30:00+08:00",
      "consecutive_failures": 0
    }
  ]
}
```

### 11.3.2 Dashboard

```text
GET /api/dashboard?instance_id={uuid}
```

响应：

```json
{
  "instance_id": "uuid",
  "snapshot_time": "2026-05-09T10:30:00+08:00",
  "collect_delay_seconds": 3,
  "metrics": {
    "session_count": 120,
    "active_request_count": 18,
    "blocked_session_count": 6,
    "root_blocker_count": 1,
    "max_blocking_duration_ms": 45000,
    "waiting_request_count": 12,
    "deadlocks_last_hour": 0
  },
  "top_waits": [],
  "top_cpu_sqls": [],
  "top_io_sqls": [],
  "top_tempdb_sessions": [],
  "recent_events": []
}
```

### 11.3.3 Session 列表

```text
GET /api/sessions?instance_id={uuid}&status=running&only_blocked=true&page=1&page_size=50&sort_by=cpu_time&sort_order=desc
```

响应字段：

1. `session_id`
2. `login_name`
3. `host_name`
4. `program_name`
5. `database_name`
6. `status`
7. `open_transaction_count`
8. `cpu_time`
9. `reads`
10. `writes`
11. `logical_reads`
12. `wait_type`
13. `wait_time_ms`
14. `blocking_session_id`
15. `current_sql_preview`

### 11.3.4 SQL 列表

```text
GET /api/sqls?instance_id={uuid}&page=1&page_size=50&sort_by=cpu_time_ms&sort_order=desc
```

响应字段：

1. `session_id`
2. `request_id`
3. `database_name`
4. `status`
5. `command`
6. `duration_ms`
7. `cpu_time_ms`
8. `logical_reads`
9. `reads`
10. `writes`
11. `wait_type`
12. `wait_time_ms`
13. `blocking_session_id`
14. `sql_hash`
15. `sql_preview`

### 11.3.5 阻塞链

```text
GET /api/blocking?instance_id={uuid}
```

响应：

```json
{
  "snapshot_time": "2026-05-09T10:30:00+08:00",
  "chains": [
    {
      "root_session_id": 88,
      "blocked_count": 6,
      "max_wait_time_ms": 45000,
      "risk_level": "high",
      "nodes": []
    }
  ]
}
```

### 11.3.6 Kill Session

```text
POST /api/kill
```

请求：

```json
{
  "instance_id": "uuid",
  "session_id": 88,
  "reason": "Root blocker caused production order timeout"
}
```

响应：

```json
{
  "audit_id": "uuid",
  "result": "success",
  "message": "Session killed"
}
```

### 11.3.7 历史回放

```text
GET /api/replay?instance_id={uuid}&time=2026-05-09T10:30:00+08:00
```

响应：

```json
{
  "requested_time": "2026-05-09T10:30:00+08:00",
  "snapshot_time": "2026-05-09T10:29:58+08:00",
  "frame_id": "uuid",
  "dashboard": {},
  "sessions": [],
  "sqls": [],
  "blocking": [],
  "waits": [],
  "tempdb": []
}
```

## 12. Kill 安全设计

## 12.1 强制校验

Kill 前必须通过以下校验：

1. 当前用户角色为 `dba` 或 `admin`。
2. `reason` 非空，长度至少 10 个字符。
3. 目标实例启用 Kill 账号。
4. 目标 session 当前仍存在。
5. 目标 session 不是当前 Kill 连接自身。
6. 目标 session 不是平台采集账号。
7. 目标 session 不是平台 Kill 账号。
8. 目标 session_id 大于 `MIN_KILLABLE_SESSION_ID`，默认 50。
9. 目标 session 未处于 `KILLED/ROLLBACK`。
10. 如果目标 session 无阻塞影响且不是高资源请求，前端提示低必要性风险。

## 12.2 风险分级

| 风险 | 条件 |
|---|---|
| low | 非活跃、无事务、无阻塞影响 |
| medium | 活跃请求或存在打开事务 |
| high | 根阻塞且影响 session >= 5 |
| critical | 打开事务持续超过 10 分钟，或影响 session >= 20 |

风险不阻止 Kill，但必须展示。

## 12.3 审计要求

无论 Kill 成功、失败或被拒绝，都写入 `kill_audits`。

`before_snapshot` 至少包含：

1. Session 基础信息。
2. 当前 SQL preview 和 hash。
3. open transaction count。
4. blocking impact count。
5. wait type。
6. cpu/read/write/logical read。
7. 采集时间。

## 13. 权限与认证设计

## 13.1 MVP 认证

MVP 使用本地账号 + JWT。

登录流程：

1. 用户提交 username/password。
2. API 校验 password hash。
3. 返回 access token。
4. 前端在请求头中携带 `Authorization: Bearer <token>`。

## 13.2 角色

| 角色 | 说明 |
|---|---|
| viewer | 只能查看基础数据 |
| developer | 可查看 SQL 详情 |
| dba | 可查看全部并执行 Kill |
| admin | 可管理实例和用户 |

## 13.3 SQL 文本可见性

| 角色 | SQL 文本 |
|---|---|
| viewer | 只看 preview 或脱敏文本 |
| developer | 可看完整 SQL |
| dba | 可看完整 SQL |
| admin | 可看完整 SQL |

## 14. 前端技术设计

## 14.1 路由

```text
/login
/dashboard
/sessions
/sqls
/blocking
/waits
/resources
/tempdb
/deadlocks
/replay
/audits/kills
/settings/instances
/settings/users
```

## 14.2 全局状态

使用 Pinia。

状态：

1. 当前用户。
2. 当前实例。
3. 实例列表。
4. 刷新间隔。
5. 是否暂停刷新。
6. 权限能力。

## 14.3 轮询策略

页面级轮询：

1. Dashboard：5 秒。
2. Sessions：5 秒。
3. SQLs：5 秒。
4. Blocking：5 秒。
5. Waits：5 秒。
6. TempDB：10 秒。
7. Deadlocks：10 秒。

切换实例、切换筛选、手动刷新时立即请求。

## 14.4 表格策略

Session 和 SQL 大表使用 vxe-table。

要求：

1. 服务端分页。
2. 服务端排序。
3. 筛选条件同步到 URL query。
4. 刷新时保留分页、排序和筛选。
5. 支持行点击打开详情抽屉。

## 14.5 错误状态

页面必须处理：

1. 实例未选择。
2. 实例采集失败。
3. 数据过期。
4. 无权限查看完整 SQL。
5. 查询超时。
6. 空数据。

## 15. 部署设计

## 15.1 目录

```text
/opt/sqlmon/
  backend/
  frontend/
  venv/
  config/
    app.env
  logs/
    api.log
    collector.log
  scripts/
    migrate.sh
    start-api.sh
    start-collector.sh
```

## 15.2 环境变量

```text
SQLMON_ENV=prod
SQLMON_SECRET_KEY=
SQLMON_DATABASE_URL=postgresql+asyncpg://sqlmon:password@127.0.0.1:5432/sqlmon
SQLMON_ENCRYPTION_KEY=
SQLMON_API_HOST=127.0.0.1
SQLMON_API_PORT=8000
SQLMON_LOG_LEVEL=INFO
SQLMON_DEFAULT_RETENTION_DAYS=7
SQLMON_COLLECT_CONNECT_TIMEOUT_SECONDS=5
SQLMON_COLLECT_QUERY_TIMEOUT_SECONDS=3
SQLMON_MIN_KILLABLE_SESSION_ID=50
```

## 15.3 systemd

API 服务：

```ini
[Unit]
Description=SQLMon API
After=network.target postgresql.service

[Service]
WorkingDirectory=/opt/sqlmon/backend
EnvironmentFile=/opt/sqlmon/config/app.env
ExecStart=/opt/sqlmon/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Collector 服务：

```ini
[Unit]
Description=SQLMon Collector
After=network.target postgresql.service

[Service]
WorkingDirectory=/opt/sqlmon/backend
EnvironmentFile=/opt/sqlmon/config/app.env
ExecStart=/opt/sqlmon/venv/bin/python -m app.collector.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 15.4 Nginx

```nginx
server {
    listen 80;
    server_name _;

    root /opt/sqlmon/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 16. 测试策略

## 16.1 单元测试

重点覆盖：

1. SQL hash 和归一化。
2. Wait 类型分类。
3. 阻塞链计算。
4. Kill 安全校验。
5. API 参数校验。
6. 历史回放快照选择。

## 16.2 集成测试

需要覆盖：

1. PostgreSQL migration。
2. API 查询最新快照。
3. Collector 写入快照。
4. Deadlock XML 解析。
5. Kill 审计写入。

## 16.3 Mock 数据

无真实 SQL Server 时，提供 Collector mock mode：

1. 生成正常 Session。
2. 生成 running request。
3. 生成阻塞链。
4. 生成高 CPU SQL。
5. 生成高 IO SQL。
6. 生成 TempDB 高占用。
7. 生成 deadlock XML 样例。

Mock mode 只写 PostgreSQL，不连接 SQL Server。

## 16.4 验收测试

P0 验收必须覆盖：

1. 添加实例并完成连接测试。
2. Collector 写入 Session / Request 快照。
3. Dashboard 展示最新指标。
4. Session 页面按状态筛选。
5. SQL 页面按 CPU、IO、耗时排序。
6. 阻塞链页面展示根阻塞。
7. Kill 被权限拒绝。
8. DBA Kill 写入审计。
9. 历史回放返回指定时间附近快照。
10. 单实例采集失败不影响其他实例。

## 17. 可观测性

## 17.1 日志

API 日志字段：

1. request_id。
2. method。
3. path。
4. status_code。
5. duration_ms。
6. user_id。

Collector 日志字段：

1. instance_id。
2. collector_name。
3. snapshot_time。
4. duration_ms。
5. row_count。
6. status。
7. error_code。

## 17.2 健康检查

API：

```text
GET /api/health
```

返回：

1. API status。
2. PostgreSQL connectivity。
3. build version。

Collector 健康通过 `instance_collect_status` 和 systemd 状态判断。

## 18. 开发边界

## 18.1 P0 必须实现

1. 本地账号登录。
2. 实例管理。
3. SQL Server 连接测试。
4. Collector 采集 Session / Request / Wait / Blocking。
5. PostgreSQL 快照写入。
6. Dashboard。
7. Session 列表和详情。
8. SQL 列表和详情。
9. 阻塞链。
10. Kill 控制和审计。
11. 历史回放基础能力。

## 18.2 P1 延后实现

1. Deadlock 捕获。
2. TempDB 专页。
3. CPU / IO 独立分析页。
4. Query Plan 按需查看。
5. 更完整根因提示。

## 18.3 P2 延后实现

1. WebSocket / SSE。
2. 告警通知。
3. Query Store 集成。
4. 自动诊断报告。
5. 文件级 IO 分析。
6. LDAP/OIDC。

## 19. 风险与处理

| 风险 | 影响 | 处理 |
|---|---|---|
| DMV 查询影响生产实例 | 被监控实例负载增加 | 控制频率、设置超时、不默认采集计划 |
| SQL Server 版本权限差异 | 采集失败 | 连接测试检测能力并展示缺失权限 |
| Ring buffer 死锁丢失 | 死锁历史不完整 | P1 支持 event file target |
| 快照表增长过快 | 查询变慢、磁盘增长 | 日分区、定期 drop 分区 |
| Kill 误操作 | 业务中断 | 角色控制、二次确认、原因必填、审计 |
| API 与 Collector 数据不同步 | 页面显示过期数据 | 返回 snapshot_time 和 collect_delay_seconds |
| 单 Collector 无 HA | Collector 进程停掉则无采集 | systemd restart，后续支持多 Collector |

## 20. 待确认事项

进入开发前建议确认：

1. 首版登录是否确定使用本地账号。
2. SQL Server 目标版本范围是否包含 SQL Server 2022。
3. Kill 功能首版是否默认启用，还是按实例开关启用。
4. SQL 文本是否允许完整落库。
5. 历史快照默认保留 7 天是否可接受。
6. P0 是否包含 Deadlock，还是按本设计放入 P1。
7. 是否允许 Collector mock mode 作为无 SQL Server 环境下的开发和验收方式。

## 21. 参考资料

1. Microsoft Learn: `sys.dm_exec_sessions` permissions require `VIEW SERVER STATE` on SQL Server 2019 and earlier, and `VIEW SERVER PERFORMANCE STATE` on SQL Server 2022 and later.
2. Microsoft Learn: `sys.dm_exec_requests` on SQL Server 2022 and later requires `VIEW SERVER PERFORMANCE STATE`.
3. Microsoft Learn: `sys.dm_os_waiting_tasks` returns current waiting tasks and documents special blocking session values such as `-2`, `-3`, and `-4`.
4. Microsoft Learn: `KILL` requires `ALTER ANY CONNECTION` on SQL Server.
5. Microsoft Learn: `system_health` Extended Events session is enabled by default and captures detected deadlocks including the deadlock graph.
