# SQL Server 实时会话监控平台实施计划

> **面向 agentic workers：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务执行本计划。步骤使用复选框（`- [ ]`）语法跟踪。

**目标：** 构建 SQL Server 实时会话监控平台 P0 版本，覆盖实例管理、快照采集、Dashboard、Session/SQL 监控、阻塞链分析、Kill 审计和历史回放。

**架构：** 前端使用 Vue 3，由 Nginx 托管；后端使用 FastAPI；采集器使用独立 Python Collector 进程；PostgreSQL 存储配置、快照、审计和历史数据。P0 使用 HTTP 轮询和 Mock Collector，不实现 Deadlock 捕获、Query Plan 查看、WebSocket/SSE、告警和 LDAP/OIDC。

**技术栈：** Vue 3、Vite、Pinia、Element Plus、vxe-table、ECharts、Python、FastAPI、SQLAlchemy 2.x、asyncpg、Alembic、pyodbc、PostgreSQL、pytest、systemd、Nginx。

---

## 1. 范围

本计划基于以下文档执行：

- `docs/sql-server-realtime-session-monitor-prd.md`
- `docs/sql-server-realtime-session-monitor-tech-design.md`

P0 包含：

1. 本地账号登录和 JWT。
2. 实例管理。
3. PostgreSQL 表结构和 Alembic 迁移。
4. FastAPI API 服务结构。
5. 独立 Python Collector 服务结构。
6. Mock Collector，用于无 SQL Server 环境下开发和验收。
7. SQL Server Collector 接口和 P0 DMV 采集。
8. Session、Request、Wait、Blocking 快照。
9. Dashboard API。
10. Session 和 SQL 列表/详情 API。
11. 阻塞链 API。
12. Kill 安全校验和审计。
13. 历史回放 API。
14. Vue 前端基础布局、实例选择器、自动刷新和 P0 页面。
15. 直接部署配置。

P0 不包含：

1. Deadlock 捕获实现。
2. Query Plan 获取。
3. TempDB 独立页面。
4. CPU/IO 独立分析页。
5. WebSocket/SSE。
6. 告警通知。
7. LDAP/OIDC。

## 2. 目标文件结构

```text
backend/
  pyproject.toml
  alembic.ini
  app/
    __init__.py
    main.py
    config.py
    logging.py
    security.py
    db/
      __init__.py
      postgres.py
      models.py
      migrations/
        env.py
        versions/
    api/
      __init__.py
      deps.py
      routes/
        __init__.py
        auth.py
        instances.py
        dashboard.py
        sessions.py
        sqls.py
        blocking.py
        replay.py
        kill.py
        audits.py
        health.py
    schemas/
      __init__.py
      common.py
      auth.py
      instances.py
      dashboard.py
      sessions.py
      sqls.py
      blocking.py
      replay.py
      kill.py
    services/
      __init__.py
      auth_service.py
      instance_service.py
      dashboard_service.py
      session_service.py
      sql_service.py
      blocking_service.py
      replay_service.py
      kill_service.py
    collector/
      __init__.py
      main.py
      scheduler.py
      instance_runner.py
      sqlserver_client.py
      sql_text.py
      blocking_graph.py
      mock_data.py
      retention.py
      collectors/
        __init__.py
        session_request_collector.py
        wait_collector.py
  tests/
    conftest.py
    unit/
    integration/

frontend/
  package.json
  vite.config.ts
  index.html
  src/
    main.ts
    App.vue
    router/index.ts
    stores/
    api/
    layouts/
    components/
    views/

deploy/
  nginx/sqlmon.conf
  systemd/sqlmon-api.service
  systemd/sqlmon-collector.service
  env/app.env.example
  scripts/migrate.sh
  scripts/start-api.sh
  scripts/start-collector.sh
```

## 3. 执行方式

采用 Subagent-Driven Development：

1. 每个任务派发一个实现 worker。
2. worker 完成后先进行规格符合性审查。
3. 规格符合后再进行代码质量审查。
4. 审查发现问题时，由同一个 worker 修复并复审。
5. 当前任务通过后，再进入下一个任务。

执行前置条件：

1. 当前项目必须是 git 仓库。
2. 必须通过 git worktree 创建隔离工作区。
3. 不在主目录直接实现代码。
4. 所有新增或修改的项目文档必须使用中文。

## 4. 任务清单

## 任务 1：后端项目骨架

**目标：** 创建 FastAPI 后端基础结构，提供 `/api/health` 健康检查，并建立 pytest 基础测试。

**文件：**

- 创建：`backend/pyproject.toml`
- 创建：`backend/app/__init__.py`
- 创建：`backend/app/main.py`
- 创建：`backend/app/config.py`
- 创建：`backend/app/logging.py`
- 创建：`backend/app/api/__init__.py`
- 创建：`backend/app/api/routes/__init__.py`
- 创建：`backend/app/api/routes/health.py`
- 创建：`backend/app/schemas/common.py`
- 创建：`backend/tests/conftest.py`
- 创建：`backend/tests/unit/test_health.py`

**步骤：**

- [ ] 创建 `pyproject.toml`，声明 Python 3.11+、FastAPI、uvicorn、pydantic-settings、SQLAlchemy、asyncpg、Alembic、pyodbc、JWT、bcrypt、APScheduler、pytest、httpx、ruff。
- [ ] 创建 `Settings` 配置对象，读取 `SQLMON_*` 环境变量。
- [ ] 创建统一 API 响应 schema：`ApiResponse`、`ErrorBody`。
- [ ] 创建 `/api/health` 路由，返回 `{"status": "ok"}`。
- [ ] 创建 `create_app()` 并注册 health route。
- [ ] 创建 pytest fixture：`api_client`。
- [ ] 编写 `test_health_returns_ok`。
- [ ] 执行 `cd backend && python3 -m pytest tests/unit/test_health.py -v`，预期 1 个测试通过。

**完成标准：**

- `/api/health` 可测试。
- 后端基础目录清晰。
- 单元测试通过。

## 任务 2：PostgreSQL 模型与 Alembic 迁移

**目标：** 建立 P0 所需数据库模型和初始迁移。

**文件：**

- 创建：`backend/alembic.ini`
- 创建：`backend/app/db/__init__.py`
- 创建：`backend/app/db/postgres.py`
- 创建：`backend/app/db/models.py`
- 创建：`backend/app/db/migrations/env.py`
- 创建：`backend/app/db/migrations/versions/0001_initial_schema.py`
- 创建：`backend/tests/unit/test_models_metadata.py`

**必须包含的表：**

1. `instances`
2. `instance_collect_status`
3. `snapshot_frames`
4. `session_snapshots`
5. `request_snapshots`
6. `wait_snapshots`
7. `blocking_snapshots`
8. `sql_texts`
9. `kill_audits`
10. `users`

**步骤：**

- [ ] 创建 async SQLAlchemy engine 和 session factory。
- [ ] 按技术设计创建 SQLAlchemy models。
- [ ] 为 `instances.status`、`kill_audits.result`、`users.role`、`users.status` 增加 CheckConstraint。
- [ ] 为 session、request、sql_texts 创建技术设计中要求的索引。
- [ ] 配置 Alembic。
- [ ] 生成并整理 `0001_initial_schema.py`。
- [ ] 编写 metadata 测试，验证核心表均已注册。
- [ ] 执行 `cd backend && python3 -m pytest tests/unit/test_models_metadata.py -v`。

**完成标准：**

- 模型名、字段名和技术设计一致。
- 初始迁移可执行。
- metadata 测试通过。

## 任务 3：认证和 API 依赖

**目标：** 实现本地账号认证、JWT 签发、当前用户依赖和角色校验。

**文件：**

- 创建：`backend/app/security.py`
- 创建：`backend/app/schemas/auth.py`
- 创建：`backend/app/services/auth_service.py`
- 创建：`backend/app/api/deps.py`
- 创建：`backend/app/api/routes/auth.py`
- 修改：`backend/app/main.py`
- 创建：`backend/tests/unit/test_auth_service.py`

**步骤：**

- [ ] 实现 `hash_password()`、`verify_password()`。
- [ ] 实现 `create_access_token()`、`decode_access_token()`。
- [ ] 创建 `LoginRequest`、`LoginResponse`。
- [ ] 实现 `authenticate_user()`。
- [ ] 创建 `current_user` 和 `require_roles()` 依赖。
- [ ] 创建 `POST /api/auth/login`。
- [ ] 注册 auth route。
- [ ] 测试密码 hash 校验和 JWT round-trip。
- [ ] 执行 `cd backend && python3 -m pytest tests/unit/test_auth_service.py -v`。

**完成标准：**

- 密码校验正确。
- JWT 可签发、解析。
- 角色依赖可复用。

## 任务 4：实例管理 API

**目标：** 实现实例列表、新增、编辑和基础连接配置存储。

**文件：**

- 创建：`backend/app/schemas/instances.py`
- 创建：`backend/app/services/instance_service.py`
- 创建：`backend/app/api/routes/instances.py`
- 修改：`backend/app/main.py`
- 创建：`backend/tests/unit/test_instance_service.py`

**步骤：**

- [ ] 创建 `InstanceCreate`、`InstanceUpdate`、`InstanceOut`。
- [ ] 实现连接串加密/解密函数。P0 可使用 base64 占位实现，但函数名和调用边界必须保留，后续可替换为真实加密。
- [ ] 实现 `list_instances()`。
- [ ] 实现 `create_instance()`，同时创建 `instance_collect_status`。
- [ ] 实现 `update_instance()`。
- [ ] 创建 `GET /api/instances`、`POST /api/instances`、`PUT /api/instances/{instance_id}`。
- [ ] 新增和编辑操作要求 admin 角色。
- [ ] 测试连接串加密/解密 round-trip。

**完成标准：**

- 实例数据不明文保存连接串。
- Admin 才能新增/编辑实例。
- 单元测试通过。

## 任务 5：Collector 工具模块

**目标：** 实现 SQL 文本处理、SQL hash、Wait 分类和阻塞链算法。

**文件：**

- 创建：`backend/app/collector/sql_text.py`
- 创建：`backend/app/collector/blocking_graph.py`
- 创建：`backend/tests/unit/test_sql_text.py`
- 创建：`backend/tests/unit/test_blocking_graph.py`

**步骤：**

- [ ] 实现 `preview_sql()`：压缩空白并截断。
- [ ] 实现 `normalize_sql()`：小写、压缩空白、替换数字和字符串字面量。
- [ ] 实现 `sql_hash()` 和 `normalized_sql_hash()`，使用 SHA-256。
- [ ] 实现 `BlockingInput`、`BlockingEdge`。
- [ ] 实现 `build_blocking_edges()`。
- [ ] 支持特殊 blocker：`-2`、`-3`、`-4`。
- [ ] 支持环检测，避免无限遍历。
- [ ] 编写 SQL normalize、hash、preview 测试。
- [ ] 编写 root blocker、chain depth、special blocker、cycle 测试。

**完成标准：**

- SQL 指纹行为稳定。
- 阻塞链算法可独立测试。
- 单元测试通过。

## 任务 6：Mock Collector 和采集器入口

**目标：** 提供无 SQL Server 环境下可写入或模拟快照的数据源，为前后端开发和验收提供基础。

**文件：**

- 创建：`backend/app/collector/mock_data.py`
- 创建：`backend/app/collector/instance_runner.py`
- 创建：`backend/app/collector/main.py`
- 创建：`backend/tests/unit/test_mock_data.py`

**步骤：**

- [ ] 创建 mock session/request 数据结构。
- [ ] 生成至少 3 个 session、2 个 request，其中 1 个 request 被阻塞。
- [ ] mock 数据包含高 CPU、高 IO、锁等待、根阻塞场景。
- [ ] 创建 `collect_instance_once()` 入口。
- [ ] 创建 Collector 主进程入口。
- [ ] 编写测试验证 mock frame 包含被阻塞请求。

**完成标准：**

- Mock 数据可用于 Dashboard、Sessions、SQL、Blocking 页面。
- Collector 主入口可启动。
- 单元测试通过。

## 任务 7：SQL Server Client 与 DMV Collector

**目标：** 实现 SQL Server 查询封装和 P0 DMV SQL 常量。

**文件：**

- 创建：`backend/app/collector/sqlserver_client.py`
- 创建：`backend/app/collector/collectors/session_request_collector.py`
- 创建：`backend/app/collector/collectors/wait_collector.py`
- 创建：`backend/tests/unit/test_sqlserver_collector_sql.py`

**步骤：**

- [ ] 封装 `SqlServerClient.query()`。
- [ ] 定义 `SESSION_REQUEST_SQL`，使用 `sys.dm_exec_sessions`、`sys.dm_exec_requests`、`sys.dm_exec_sql_text`。
- [ ] 定义 `WAIT_SQL`，使用 `sys.dm_os_waiting_tasks`。
- [ ] 实现 `categorize_wait()`。
- [ ] 测试 SQL 常量包含预期 DMV。
- [ ] 测试 Wait 分类：Lock、IO、Log、CPU、Parallelism、Memory、TempDB、Network、Other。

**完成标准：**

- SQL Server 查询封装独立。
- DMV SQL 与技术设计一致。
- 单元测试通过。

## 任务 8：核心查询服务

**目标：** 实现 Dashboard、Session、SQL、Blocking、Replay 的服务层查询。

**文件：**

- 创建：`backend/app/services/dashboard_service.py`
- 创建：`backend/app/services/session_service.py`
- 创建：`backend/app/services/sql_service.py`
- 创建：`backend/app/services/blocking_service.py`
- 创建：`backend/app/services/replay_service.py`
- 创建：`backend/app/schemas/dashboard.py`
- 创建：`backend/app/schemas/sessions.py`
- 创建：`backend/app/schemas/sqls.py`
- 创建：`backend/app/schemas/blocking.py`
- 创建：`backend/app/schemas/replay.py`

**步骤：**

- [ ] 实现 `get_latest_frame()` 公共查询逻辑。
- [ ] Dashboard 查询 session 数、活跃 request 数、阻塞数、Top Wait、Top CPU SQL、Top IO SQL。
- [ ] Session 查询支持分页、状态筛选、只看阻塞、只看打开事务。
- [ ] SQL 查询支持分页和排序：耗时、CPU、逻辑读、读、写、等待时间。
- [ ] Blocking 查询按 root session 分组，按影响面和最大等待时间排序。
- [ ] Replay 查询目标时间之前最近 frame，默认最大偏差 10 秒。
- [ ] 为每个服务创建 schema。
- [ ] 使用集成测试种子数据验证排序、筛选和聚合。

**完成标准：**

- 服务层不依赖前端。
- 所有查询按 `instance_id` 和 `frame_id/snapshot_time` 限定。
- 集成测试覆盖关键聚合。

## 任务 9：实时页面 API Routes

**目标：** 暴露 Dashboard、Sessions、SQLs、Blocking、Replay API。

**文件：**

- 创建：`backend/app/api/routes/dashboard.py`
- 创建：`backend/app/api/routes/sessions.py`
- 创建：`backend/app/api/routes/sqls.py`
- 创建：`backend/app/api/routes/blocking.py`
- 创建：`backend/app/api/routes/replay.py`
- 修改：`backend/app/main.py`

**步骤：**

- [ ] 创建 `GET /api/dashboard?instance_id=`。
- [ ] 创建 `GET /api/sessions` 和 `GET /api/sessions/{session_id}`。
- [ ] 创建 `GET /api/sqls` 和 `GET /api/sqls/{sql_hash}`。
- [ ] 创建 `GET /api/blocking?instance_id=`。
- [ ] 创建 `GET /api/replay?instance_id=&time=`。
- [ ] 所有接口要求认证。
- [ ] 无最新 frame 时返回明确错误。
- [ ] 注册所有 route。
- [ ] 执行后端单元和集成测试。

**完成标准：**

- API 参数和技术设计一致。
- API 错误清晰。
- 测试通过。

## 任务 10：Kill 安全校验与审计 API

**目标：** 实现 Kill 请求校验、执行边界和审计记录。

**文件：**

- 创建：`backend/app/schemas/kill.py`
- 创建：`backend/app/services/kill_service.py`
- 创建：`backend/app/api/routes/kill.py`
- 创建：`backend/app/api/routes/audits.py`
- 修改：`backend/app/main.py`
- 创建：`backend/tests/unit/test_kill_service.py`

**步骤：**

- [ ] 创建 `KillRequest` 和 `KillResponse`。
- [ ] 实现 `KillTarget`。
- [ ] 实现 `validate_kill_target()`。
- [ ] 拒绝原因少于 10 个字符。
- [ ] 拒绝系统 session。
- [ ] 拒绝平台采集账号和 Kill 账号。
- [ ] 拒绝 `KILLED/ROLLBACK`。
- [ ] 创建 `POST /api/kill`，仅允许 dba/admin。
- [ ] Kill 成功、失败、拒绝均写入 `kill_audits`。
- [ ] 创建 `GET /api/audits/kills`，仅允许 dba/admin。
- [ ] 编写 Kill 校验单元测试。

**完成标准：**

- Kill 不绕过权限。
- Kill 不绕过安全校验。
- 审计完整。
- 单元测试通过。

## 任务 11：前端项目骨架

**目标：** 创建 Vue 3 前端基础工程、路由、API client、状态管理和主布局。

**文件：**

- 创建：`frontend/package.json`
- 创建：`frontend/vite.config.ts`
- 创建：`frontend/index.html`
- 创建：`frontend/src/main.ts`
- 创建：`frontend/src/App.vue`
- 创建：`frontend/src/router/index.ts`
- 创建：`frontend/src/api/client.ts`
- 创建：`frontend/src/stores/auth.ts`
- 创建：`frontend/src/stores/instances.ts`
- 创建：`frontend/src/stores/refresh.ts`
- 创建：`frontend/src/layouts/MainLayout.vue`

**步骤：**

- [ ] 创建 Vite + Vue 3 工程配置。
- [ ] 引入 Pinia、Vue Router、Element Plus、vxe-table、ECharts。
- [ ] 创建 axios API client，自动携带 JWT。
- [ ] 创建路由：login、dashboard、sessions、sqls、blocking、replay、settings/instances。
- [ ] 创建主布局，包含侧边导航和内容区。
- [ ] 创建 auth、instances、refresh store。
- [ ] 执行 `cd frontend && npm install && npm run build`。

**完成标准：**

- 前端能构建。
- 路由结构完整。
- API client 可复用。

## 任务 12：前端 P0 页面

**目标：** 实现 P0 监控页面和共享组件。

**文件：**

- 创建：`frontend/src/components/InstanceSelector.vue`
- 创建：`frontend/src/components/AutoRefreshControl.vue`
- 创建：`frontend/src/components/DataState.vue`
- 创建：`frontend/src/components/SessionDetailDrawer.vue`
- 创建：`frontend/src/components/KillConfirmDialog.vue`
- 创建：`frontend/src/views/LoginView.vue`
- 创建：`frontend/src/views/DashboardView.vue`
- 创建：`frontend/src/views/SessionsView.vue`
- 创建：`frontend/src/views/SqlsView.vue`
- 创建：`frontend/src/views/BlockingView.vue`
- 创建：`frontend/src/views/ReplayView.vue`
- 创建：`frontend/src/views/InstancesView.vue`

**步骤：**

- [ ] 实现登录页。
- [ ] 实现实例选择器。
- [ ] 实现自动刷新控件。
- [ ] 实现数据状态组件：加载、空数据、错误、数据过期。
- [ ] Dashboard 展示核心指标、Top Wait、Top SQL。
- [ ] Sessions 页面使用 vxe-table，支持筛选和详情抽屉。
- [ ] SQL 页面使用 vxe-table，支持服务端排序。
- [ ] Blocking 页面按根阻塞分组展示链路。
- [ ] Replay 页面支持选择时间并展示历史 frame。
- [ ] Kill 确认弹窗要求输入原因。
- [ ] 执行 `cd frontend && npm run build`。

**完成标准：**

- P0 页面可访问。
- 刷新时保留筛选、分页和排序。
- 前端构建通过。

## 任务 13：直接部署文件

**目标：** 提供 Linux 直接部署所需配置。

**文件：**

- 创建：`deploy/env/app.env.example`
- 创建：`deploy/systemd/sqlmon-api.service`
- 创建：`deploy/systemd/sqlmon-collector.service`
- 创建：`deploy/nginx/sqlmon.conf`
- 创建：`deploy/scripts/migrate.sh`
- 创建：`deploy/scripts/start-api.sh`
- 创建：`deploy/scripts/start-collector.sh`

**步骤：**

- [ ] 创建环境变量示例。
- [ ] 创建 API systemd service。
- [ ] 创建 Collector systemd service。
- [ ] 创建 Nginx 配置，托管前端并反向代理 `/api`。
- [ ] 创建迁移脚本。
- [ ] 创建 API 启动脚本。
- [ ] 创建 Collector 启动脚本。
- [ ] 执行 `bash -n deploy/scripts/*.sh`。

**完成标准：**

- 部署文件路径和技术设计一致。
- 脚本语法检查通过。

## 任务 14：P0 端到端验收

**目标：** 建立 P0 验收清单和后端集成验收测试。

**文件：**

- 创建：`backend/tests/integration/test_p0_acceptance.py`
- 创建：`docs/p0-acceptance-checklist.md`

**步骤：**

- [ ] 创建中文 P0 验收清单。
- [ ] 集成测试种子数据包含两个实例，其中一个成功采集，一个采集失败。
- [ ] 种子数据包含一个 frame、三个 session、两个 request、一个 blocking edge、一个 wait aggregate。
- [ ] 验证 Dashboard 计数正确。
- [ ] 验证 Session 列表返回三行。
- [ ] 验证 SQL 列表返回两行。
- [ ] 验证 Blocking API 返回一个根阻塞链。
- [ ] 验证 Replay 返回目标时间之前最近 frame。
- [ ] 执行 `cd backend && python3 -m pytest -v`。
- [ ] 执行 `cd frontend && npm run build`。

**完成标准：**

- 中文验收清单存在。
- 后端测试通过。
- 前端构建通过。

## 5. 计划自检

需求覆盖：

1. 多实例管理：任务 2、4、11、12。
2. Dashboard：任务 8、9、12。
3. Session 监控：任务 7、8、9、12。
4. SQL 监控：任务 7、8、9、12。
5. 阻塞链分析：任务 5、8、9、12。
6. Wait 分析：任务 7、8、9。
7. Kill 控制和审计：任务 10。
8. 历史回放：任务 8、9、12。
9. 直接部署：任务 13。
10. Deadlock 捕获：明确排除在 P0，按技术设计进入 P1。

执行约束：

1. 所有相关文档必须使用中文。
2. 代码标识符、API 路径、数据库字段名可以使用英文。
3. 用户可见文案优先使用中文。
4. 不在非 git 仓库中启动 Subagent-Driven 实现。
5. 不在未创建隔离 worktree 的情况下启动实现。

## 6. 执行交接

计划已完成并保存到：

```text
docs/superpowers/plans/2026-05-09-sql-server-realtime-session-monitor.md
```

执行方式已选择：

```text
Subagent-Driven（推荐）
```

当前阻塞：

```text
/Users/chenxuan/sql 不是 git 仓库，无法创建 git worktree。
```

需要先确认：

1. 在 `/Users/chenxuan/sql` 初始化 git 仓库后继续。
2. 或者切换到已有 git 仓库路径后继续。
