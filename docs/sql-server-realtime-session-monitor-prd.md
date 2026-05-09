# SQL Server 实时会话监控平台 PRD

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 产品名称 | SQL Server 实时会话监控平台 |
| 产品阶段 | MVP |
| 产品定位 | 单团队内部 DBA 排障工具 |
| 前端技术栈 | Vue 3 + Vite + 表格组件 + 图表组件 |
| 后端技术栈 | Python + FastAPI |
| 存储 | PostgreSQL |
| 部署方式 | 内网 Linux 服务器直接部署 |
| 目标用户 | DBA、后端研发、运维/SRE |

## 2. 产品背景

SQL Server 线上问题通常具有突发性和现场依赖性。阻塞、长事务、高 CPU SQL、高 IO SQL、TempDB 异常和死锁问题一旦发生，如果没有及时采集现场，事后往往只能依赖零散日志、人工登录服务器、手写 DMV 查询和经验判断。

当前需要建设一个内部实时监控平台，统一接入多个 SQL Server 实例，帮助 DBA 在一个页面内完成实时观察、阻塞定位、SQL 分析、资源分析、Kill 处置和历史回放。

## 3. 产品目标

### 3.1 核心目标

1. 实时可视化 SQL Server 当前运行状态。
2. 支持多个数据库实例统一监控和切换。
3. 实时展示 Session、Request、SQL、Wait、Blocking、TempDB、Deadlock 等关键诊断数据。
4. 快速定位根阻塞 Session、高 CPU SQL、高 IO SQL、长事务和异常等待。
5. 支持 DBA 安全 Kill Session，并保留操作审计。
6. 保存短期历史快照，支持问题复盘和历史回放。

### 3.2 MVP 成功标准

1. DBA 可以在 3 分钟内发现并定位一个实时阻塞问题。
2. DBA 可以清晰识别根阻塞 Session 及其 SQL、事务和影响范围。
3. DBA 可以按 CPU、IO、执行时长、等待时间快速定位异常 SQL。
4. DBA 可以查看最近 24 小时内某一时刻的问题现场。
5. 平台可以稳定接入至少 3 个 SQL Server 实例。
6. 单个实例采集失败不影响其他实例。

## 4. 产品范围

### 4.1 MVP 包含

| 能力 | 说明 | 优先级 |
|---|---|---|
| 多实例管理 | 接入、编辑、禁用、切换 SQL Server 实例 | P0 |
| 实时 Dashboard | 展示实例健康、连接、阻塞、Wait、Top SQL | P0 |
| 实时 Session 监控 | 展示当前连接、状态、事务、等待、资源使用 | P0 |
| 实时 SQL 监控 | 展示正在执行 SQL、耗时、CPU、IO、等待 | P0 |
| 阻塞链分析 | 展示阻塞树、根阻塞、影响范围 | P0 |
| Wait 分析 | 展示当前等待分布和关联 Session/SQL | P0 |
| Kill 控制 | DBA 执行 Kill，二次确认，审计记录 | P0 |
| 历史回放 | 保存短期快照，按时间复现现场 | P0 |
| CPU 分析 | 高 CPU SQL、Session 排名和详情 | P1 |
| IO 分析 | 高逻辑读、物理读、写入 SQL 排名 | P1 |
| TempDB 分析 | TempDB 占用 Session、SQL、等待 | P1 |
| 死锁监控 | 捕获死锁事件，展示 XML 和摘要 | P1 |
| 根因提示 | 基于规则生成疑似原因和检查建议 | P1 |
| 基础权限 | Viewer、Developer、DBA、Admin | P1 |

### 4.2 MVP 不包含

1. 不支持 SQL Server 之外的数据库。
2. 不做 SaaS 多租户。
3. 不做完整告警平台。
4. 不做自动 SQL 改写。
5. 不做容量预测。
6. 不做复杂审批流。
7. 不做完整商业化报表。

## 5. 用户角色

### 5.1 DBA

核心用户。负责实时排障、阻塞分析、Kill 操作、死锁分析和历史复盘。

主要诉求：

1. 快速发现线上数据库异常。
2. 找到根阻塞和异常 SQL。
3. 判断问题影响范围。
4. 安全执行 Kill。
5. 事后复盘问题现场。

### 5.2 后端研发

辅助用户。负责定位业务服务产生的 SQL 和配合优化。

主要诉求：

1. 查看自己服务发起的 SQL。
2. 分析 SQL 的耗时、等待、CPU、IO。
3. 了解 SQL 是否造成阻塞或资源压力。

### 5.3 运维/SRE

辅助用户。负责判断数据库异常是否影响业务系统。

主要诉求：

1. 查看实例整体健康。
2. 查看阻塞、死锁、连接数和资源异常。
3. 协同 DBA 处理故障。

## 6. 典型场景

### 6.1 实时阻塞排查

1. DBA 打开 Dashboard。
2. 平台提示当前实例存在严重阻塞。
3. DBA 点击进入阻塞链页面。
4. 平台展示根阻塞 Session、被阻塞 Session 数、最长等待时间、当前 SQL、事务状态和锁资源。
5. DBA 打开根阻塞详情，判断是否为未提交事务或长事务。
6. 如需处置，DBA 输入原因并 Kill Session。
7. 平台记录 Kill 审计，并刷新阻塞链状态。

### 6.2 高 CPU SQL 排查

1. DBA 进入 SQL 监控页面。
2. 按 CPU 时间倒序。
3. 打开 Top SQL 详情。
4. 查看 SQL 文本、Session 来源、执行时长、CPU 时间、等待类型、逻辑读和查询计划。
5. 判断该 SQL 是 CPU 密集、等待密集还是 IO 密集。

### 6.3 TempDB 异常排查

1. DBA 发现 Dashboard 中 TempDB 使用异常。
2. 进入 TempDB 页面。
3. 查看 Top TempDB Session 和 SQL。
4. 判断是否存在排序、Hash、临时表或版本存储压力。
5. 关联 Wait 类型判断是否存在 TempDB 争用。

### 6.4 死锁复盘

1. 平台捕获死锁事件。
2. DBA 进入死锁页面。
3. 查看发生时间、victim、参与 Session、SQL 文本、锁资源和 deadlock XML。
4. DBA 根据历史快照回放死锁发生前后的 Session 状态。

## 7. 总体架构

### 7.1 技术栈

| 层级 | 技术 |
|---|---|
| 前端框架 | Vue 3 + Vite |
| UI 组件 | Element Plus 或 Naive UI |
| 大表格 | vxe-table |
| 图表 | Apache ECharts |
| 后端框架 | Python + FastAPI |
| SQL Server 连接 | pyodbc + Microsoft ODBC Driver 18 |
| PostgreSQL 访问 | SQLAlchemy 2.x + asyncpg |
| 后台任务 | APScheduler |
| 存储 | PostgreSQL |
| 部署 | Linux + Nginx + systemd |

### 7.2 部署架构

```text
Browser
  |
  | HTTP
  v
Nginx
  |
  | /api
  v
FastAPI Backend
  |
  | read/write
  v
PostgreSQL

Collector Worker
  |
  | pyodbc
  v
SQL Server Instances

Collector Worker
  |
  | snapshots/events
  v
PostgreSQL
```

### 7.3 服务划分

| 服务 | 说明 |
|---|---|
| sqlmon-api | FastAPI 后端，提供 API、权限、Kill、实例管理 |
| sqlmon-collector | Python 采集器，采集 DMV、阻塞、Wait、TempDB、死锁 |
| nginx | 托管前端静态文件，反向代理 API |
| postgresql | 存储配置、快照、事件和审计 |

## 8. 功能需求

## 8.1 多实例管理

### 功能说明

平台支持配置多个 SQL Server 实例。用户可在全局实例选择器中切换当前实例，所有监控页面随实例切换刷新。

### 实例字段

| 字段 | 说明 |
|---|---|
| instance_id | 实例唯一 ID |
| instance_name | 实例名称 |
| host | 主机地址 |
| port | 端口 |
| database | 默认数据库 |
| environment | prod、staging、dev |
| business_owner | 业务负责人 |
| dba_owner | DBA 负责人 |
| version | SQL Server 版本 |
| status | online、offline、collect_error、disabled |
| collect_interval | 采集间隔 |
| last_collect_time | 最近采集时间 |

### 功能点

1. 新增实例。
2. 编辑实例。
3. 禁用实例。
4. 删除实例，需二次确认。
5. 实例连接测试。
6. 实例搜索。
7. 按环境筛选。
8. 显示采集状态和最近采集时间。

### 验收标准

1. Admin 可以新增、编辑、禁用实例。
2. 用户可以在所有监控页面切换实例。
3. 实例切换后页面数据正确刷新。
4. 实例连接失败时展示明确错误。

## 8.2 实时 Dashboard

### 功能说明

Dashboard 用于展示当前实例的核心健康状态，让用户快速判断是否存在紧急风险。

### 指标

| 指标 | 说明 |
|---|---|
| 当前连接数 | 当前 Session 总数 |
| 活跃请求数 | 当前 active request 数 |
| 阻塞 Session 数 | 当前被阻塞 Session 数 |
| 根阻塞数 | 阻塞别人但自身未被阻塞的 Session 数 |
| 最长阻塞时长 | 当前最长阻塞持续时间 |
| 当前等待数 | 当前存在 wait 的请求数 |
| Top Wait Type | 当前最主要等待类型 |
| Top CPU SQL | CPU 时间最高 SQL |
| Top IO SQL | 逻辑读或物理读最高 SQL |
| Top TempDB Session | TempDB 使用最高 Session |
| 最近死锁数 | 最近 1 小时死锁数量 |

### 页面区域

1. 实例状态栏。
2. 健康指标卡片。
3. 阻塞风险区。
4. Top SQL 区。
5. Wait 分布图。
6. CPU/IO 趋势图。
7. 最近事件列表。

### 刷新策略

1. 默认 5 秒自动刷新。
2. 支持 1 秒、3 秒、5 秒、10 秒刷新间隔。
3. 支持暂停刷新。
4. 展示最近刷新时间。
5. 采集延迟超过 15 秒时提示数据可能不新鲜。

### 验收标准

1. 用户进入页面后可以看到当前实例健康状态。
2. 阻塞、死锁、高资源 SQL 在首页可见。
3. 暂停刷新后页面数据不再变化。
4. 自动刷新不清空当前筛选条件。

## 8.3 实时 Session 监控

### 功能说明

展示当前实例所有 Session 及其连接来源、状态、事务、等待和资源使用。

### 列表字段

| 字段 | 说明 |
|---|---|
| session_id | SQL Server Session ID |
| login_name | 登录用户 |
| host_name | 客户端主机 |
| program_name | 应用名称 |
| database_name | 当前数据库 |
| status | Session 状态 |
| open_transaction_count | 打开事务数 |
| login_time | 登录时间 |
| last_request_start_time | 最近请求开始时间 |
| last_request_end_time | 最近请求结束时间 |
| cpu_time | 累计 CPU |
| reads | 累计读 |
| writes | 累计写 |
| logical_reads | 逻辑读 |
| blocking_session_id | 阻塞源 |
| wait_type | 当前等待类型 |
| wait_time_ms | 当前等待时长 |
| current_sql | 当前 SQL 摘要 |

### 筛选

1. 状态。
2. 数据库。
3. 登录用户。
4. 应用名。
5. 只看活跃 Session。
6. 只看被阻塞 Session。
7. 只看存在打开事务的 Session。
8. 只看高 CPU Session。
9. 只看高 IO Session。

### 操作

1. 查看 Session 详情。
2. 查看当前 SQL。
3. 查看等待信息。
4. 查看事务信息。
5. 查看锁信息。
6. 查看执行计划。
7. Kill Session。

### 验收标准

1. 页面能展示当前实例所有 Session。
2. 用户可以快速筛选活跃、阻塞、长事务 Session。
3. Sleeping 且 open_transaction_count > 0 的 Session 必须明显标识。
4. Session 详情能关联 SQL、等待、阻塞、事务和资源使用。

## 8.4 实时 SQL 监控

### 功能说明

展示当前正在执行的 SQL 请求，帮助识别长时间运行、高 CPU、高 IO 和高等待 SQL。

### 列表字段

| 字段 | 说明 |
|---|---|
| request_id | 请求 ID |
| session_id | Session ID |
| database_name | 数据库 |
| status | 请求状态 |
| command | 命令类型 |
| sql_text | SQL 文本摘要 |
| normalized_sql_hash | SQL 指纹 |
| start_time | 开始时间 |
| duration_ms | 执行时长 |
| cpu_time_ms | CPU 时间 |
| total_elapsed_time_ms | 总耗时 |
| reads | 读 |
| writes | 写 |
| logical_reads | 逻辑读 |
| row_count | 返回行数 |
| wait_type | 等待类型 |
| wait_time_ms | 等待时间 |
| blocking_session_id | 阻塞源 |
| percent_complete | 完成百分比 |

### 功能点

1. 按执行时长排序。
2. 按 CPU 排序。
3. 按逻辑读排序。
4. 按读写量排序。
5. 按等待时间排序。
6. 查看完整 SQL。
7. 复制 SQL。
8. 格式化 SQL。
9. 查看来源 Session。
10. 查看查询计划。
11. 查看同 SQL 指纹历史表现。

### SQL 文本处理

1. 默认展示前 300 字。
2. 支持展开完整 SQL。
3. SQL 文本生成 hash。
4. 可配置是否保存完整 SQL。
5. 可配置 SQL 文本脱敏。

### 验收标准

1. 正在执行 SQL 能实时出现在页面中。
2. 用户可以按 CPU、IO、耗时和等待快速排序。
3. SQL 详情页可以关联 Session、Wait、Blocking 和 Query Plan。

## 8.5 阻塞链分析

### 功能说明

实时分析 Session 之间的 blocking 关系，并以树状结构展示阻塞链。

### 核心概念

| 概念 | 说明 |
|---|---|
| 根阻塞 Session | 阻塞别人但自身未被阻塞 |
| 被阻塞 Session | blocking_session_id 不为 0 |
| 阻塞链深度 | 从根阻塞到叶子 Session 的层级 |
| 阻塞影响面 | 被同一根阻塞影响的 Session 数 |
| 阻塞持续时间 | 当前阻塞关系持续时间 |

### 功能点

1. 展示所有阻塞链。
2. 高亮根阻塞 Session。
3. 展示每条链的影响 Session 数。
4. 展示最长等待时间。
5. 展示根阻塞 SQL。
6. 展示被阻塞 SQL。
7. 展示锁资源。
8. 按影响面排序。
9. 跳转 Session 详情。
10. 对根阻塞执行 Kill。

### 根因提示规则

| 场景 | 提示 |
|---|---|
| 根阻塞 Session 正在 sleeping 且 open_transaction_count > 0 | 疑似未提交事务 |
| 根阻塞执行时间很长 | 疑似长事务或大查询 |
| 多个 Session 等待同一对象锁 | 疑似热点表或批量更新 |
| wait_type 为 LCK_M_* | 锁等待 |
| 根阻塞来自应用连接池 | 建议联系应用负责人 |

### 验收标准

1. 阻塞发生后页面能展示完整阻塞树。
2. 根阻塞 Session 必须清晰标识。
3. Kill 前必须展示影响范围和风险提示。

## 8.6 Wait 分析

### 功能说明

展示当前请求的等待类型，帮助判断瓶颈方向。

### Wait 分类

| 分类 | 示例 |
|---|---|
| Lock | LCK_M_S、LCK_M_X、LCK_M_U |
| IO | PAGEIOLATCH_*、IO_COMPLETION |
| Log | WRITELOG |
| CPU | SOS_SCHEDULER_YIELD |
| Parallelism | CXPACKET、CXCONSUMER |
| Memory | RESOURCE_SEMAPHORE |
| TempDB | PAGELATCH_* |
| Network | ASYNC_NETWORK_IO |

### 功能点

1. 当前 Wait 分布图。
2. Wait Top 列表。
3. 按 Wait 类型查看 Session。
4. 按 Wait 类型查看 SQL。
5. Wait 类型中文解释。
6. 基础排查建议。

### 验收标准

1. Dashboard 展示当前主要 Wait。
2. 用户能从 Wait 类型跳转到相关 Session 和 SQL。
3. 常见 Wait 类型有中文解释和排查方向。

## 8.7 CPU 分析

### 功能说明

识别当前 CPU 消耗高的请求、SQL 和 Session。

### 功能点

1. Top CPU SQL。
2. Top CPU Session。
3. CPU 时间排序。
4. 执行时长与 CPU 时间对比。
5. SQL 指纹聚合。
6. 查询计划入口。
7. 历史 CPU 消耗趋势。

### 判断规则

| 条件 | 说明 |
|---|---|
| cpu_time_ms 高 | 当前请求 CPU 消耗高 |
| cpu_time_ms / duration_ms 高 | CPU 密集型 SQL |
| duration_ms 高但 cpu_time_ms 低 | 可能主要在等待资源 |
| 同 SQL 指纹频繁出现 | 高频消耗 SQL |

### 验收标准

1. 用户可以看到当前 CPU Top SQL。
2. 用户可以判断 SQL 是 CPU 密集还是等待密集。
3. SQL 详情能展示 CPU、耗时、等待、IO 的组合视角。

## 8.8 IO 分析

### 功能说明

识别当前高逻辑读、高物理读、高写入 SQL。

### 功能点

1. Top Logical Reads SQL。
2. Top Physical Reads SQL。
3. Top Writes SQL。
4. Session IO 排名。
5. SQL IO 趋势。
6. 数据库级 IO 概览。
7. 文件级 IO 概览，P2。

### 判断规则

| 条件 | 说明 |
|---|---|
| logical_reads 高 | 可能缺索引或大范围扫描 |
| reads 高 | 可能物理 IO 压力 |
| writes 高 | 可能大事务或批量写入 |
| PAGEIOLATCH_* 高 | 可能 IO 瓶颈 |

### 验收标准

1. 用户可以快速定位 IO 消耗最高 SQL。
2. SQL 详情能展示逻辑读、物理读和写入量。
3. IO 分析能关联 Wait 类型。

## 8.9 TempDB 分析

### 功能说明

分析当前 TempDB 使用情况，定位占用 TempDB 的 Session、SQL 和疑似 Spill 风险。

### 指标

| 字段 | 说明 |
|---|---|
| session_id | Session ID |
| user_objects_alloc_page_count | 用户对象分配页数 |
| internal_objects_alloc_page_count | 内部对象分配页数 |
| user_objects_dealloc_page_count | 用户对象释放页数 |
| internal_objects_dealloc_page_count | 内部对象释放页数 |
| tempdb_alloc_mb | 分配 MB |
| tempdb_current_mb | 当前净使用 MB |
| sql_text | 当前 SQL |
| wait_type | 等待类型 |

### 功能点

1. 当前 TempDB 总使用量。
2. Top TempDB Session。
3. Top TempDB SQL。
4. internal/user object 拆分。
5. 疑似 Spill 标识。
6. TempDB 争用 Wait 标识。

### 验收标准

1. 用户可以看到当前 TempDB 使用最高 Session。
2. 用户可以关联到具体 SQL。
3. TempDB 相关 Wait 能被标识。

## 8.10 死锁监控

### 功能说明

实时捕获 SQL Server 死锁事件，并保存死锁详情用于分析。

### 数据来源

优先使用 Extended Events。

采集内容：

1. 死锁发生时间。
2. deadlock XML。
3. victim process。
4. 参与 process。
5. SQL 文本。
6. 登录用户。
7. 主机。
8. 应用名。
9. 数据库。
10. 锁资源。

### 功能点

1. 死锁列表。
2. 死锁详情。
3. XML 原文查看。
4. 图形化关系展示。
5. Victim 高亮。
6. SQL 文本查看。
7. 历史筛选。

### 验收标准

1. 发生死锁后平台能捕获事件。
2. 用户可以看到 victim 和参与方。
3. 用户可以查看 deadlock XML。
4. 用户可以按实例、数据库、时间筛选死锁记录。

## 8.11 Kill 控制

### 功能说明

允许有权限的 DBA 在平台内执行 Kill Session 操作。

### 安全策略

1. 默认只有 DBA 和 Admin 可 Kill。
2. Kill 前必须二次确认。
3. Kill 前展示 Session 信息。
4. Kill 前展示当前 SQL。
5. Kill 前展示阻塞影响面。
6. Kill 前展示事务状态。
7. 禁止 Kill 系统 Session。
8. 禁止 Kill 平台采集账号自身 Session。
9. 所有 Kill 操作必须审计。

### Kill 确认信息

| 信息 | 说明 |
|---|---|
| instance_name | 实例 |
| session_id | Session |
| login_name | 登录用户 |
| host_name | 来源主机 |
| program_name | 应用 |
| database_name | 数据库 |
| open_transaction_count | 打开事务数 |
| blocking_impact_count | 被影响 Session 数 |
| sql_text | 当前 SQL |
| risk_level | 风险等级 |

### 审计字段

| 字段 | 说明 |
|---|---|
| action_id | 操作 ID |
| operator | 操作人 |
| instance_id | 实例 |
| session_id | 被 Kill Session |
| reason | 操作原因 |
| before_snapshot | Kill 前快照 |
| result | 成功或失败 |
| error_message | 错误信息 |
| created_at | 操作时间 |

### 验收标准

1. 非 DBA 用户不可执行 Kill。
2. DBA Kill 前必须输入原因。
3. Kill 成功或失败都有明确反馈。
4. Kill 操作可在审计页查询。

## 8.12 历史回放

### 功能说明

按时间回放实例历史状态，用于问题复现。

### MVP 范围

保留最近 1-7 天核心快照。

包括：

1. Session 快照。
2. Request 快照。
3. Wait 快照。
4. Blocking 快照。
5. SQL 快照。
6. TempDB 快照。
7. Deadlock 事件。
8. Kill 操作审计。

### 页面能力

1. 选择实例。
2. 选择时间范围。
3. 时间轴拖动。
4. 查看某一时刻 Session。
5. 查看某一时刻阻塞链。
6. 查看某一时刻 Top SQL。
7. 查看事件列表。
8. 从死锁或阻塞事件跳转到对应时间点。

### 采样策略

| 数据类型 | 默认采样 |
|---|---|
| Session / Request | 5 秒 |
| Blocking | 5 秒 |
| Wait | 5 秒 |
| TempDB | 10 秒 |
| Deadlock | 事件触发 |
| Kill 审计 | 操作触发 |

### 验收标准

1. 用户可以选择过去时间点查看快照。
2. 用户可以复现某次阻塞链。
3. 用户可以查看过去 Top SQL。
4. 历史数据过期后自动清理。

## 9. 页面设计

## 9.1 全局布局

顶部栏：

1. 当前实例选择器。
2. 环境标签。
3. 实例状态。
4. 最近采集时间。
5. 自动刷新开关。
6. 刷新间隔选择。
7. 手动刷新按钮。

侧边导航：

1. 总览。
2. Sessions。
3. SQL。
4. 阻塞链。
5. Wait。
6. CPU / IO。
7. TempDB。
8. 死锁。
9. 历史回放。
10. 审计。
11. 实例管理。

## 9.2 Session 详情抽屉

Session 详情作为统一抽屉，从 Session、SQL、阻塞链、历史回放等页面打开。

包含：

1. 基础信息。
2. 当前 SQL。
3. 当前等待。
4. 阻塞关系。
5. 锁信息。
6. 事务信息。
7. 资源使用。
8. Kill 操作。
9. 历史轨迹。

## 9.3 SQL 详情页

包含：

1. SQL 文本。
2. Session 来源。
3. 当前执行状态。
4. CPU / IO / Wait 指标。
5. 阻塞信息。
6. 执行计划。
7. 同 SQL 指纹历史。
8. 复制 SQL。
9. 格式化 SQL。

## 10. 数据采集设计

## 10.1 数据来源

MVP 主要使用 SQL Server DMV 和 Extended Events。

### DMV

建议采集：

1. `sys.dm_exec_sessions`
2. `sys.dm_exec_requests`
3. `sys.dm_exec_connections`
4. `sys.dm_exec_sql_text`
5. `sys.dm_exec_query_plan`
6. `sys.dm_os_waiting_tasks`
7. `sys.dm_tran_locks`
8. `sys.dm_tran_session_transactions`
9. `sys.dm_db_task_space_usage`
10. `sys.dm_db_session_space_usage`
11. `sys.dm_io_virtual_file_stats`
12. `sys.dm_os_performance_counters`

### Extended Events

用于：

1. 死锁捕获。
2. 可选采集长 SQL。
3. 可选采集错误事件。

## 10.2 采集频率

| 数据 | 频率 |
|---|---|
| Session | 5 秒 |
| Request | 5 秒 |
| Blocking | 5 秒 |
| Wait | 5 秒 |
| TempDB | 10 秒 |
| Instance Health | 10 秒 |
| Deadlock | 事件触发 |

## 10.3 采集约束

1. 单实例采集 SQL 执行时间目标小于 1 秒。
2. 采集账号只授予必要只读权限。
3. Kill 使用单独权限账号。
4. 默认不持续采集完整执行计划。
5. SQL 文本按需展开，历史可配置是否保存完整 SQL。
6. 每个实例采集失败不能影响其他实例。
7. Collector 应记录每个实例采集成功、失败、耗时和错误原因。

## 11. 数据模型

## 11.1 instances

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 实例 ID |
| name | varchar | 实例名称 |
| host | varchar | 主机 |
| port | int | 端口 |
| database_name | varchar | 默认数据库 |
| environment | varchar | 环境 |
| encrypted_dsn | text | 加密连接信息 |
| status | varchar | 状态 |
| collect_interval | int | 采集间隔 |
| last_collect_time | timestamptz | 最近采集时间 |
| created_at | timestamptz | 创建时间 |
| updated_at | timestamptz | 更新时间 |

## 11.2 session_snapshots

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 快照 ID |
| instance_id | uuid | 实例 ID |
| snapshot_time | timestamptz | 快照时间 |
| session_id | int | Session ID |
| login_name | varchar | 登录名 |
| host_name | varchar | 主机 |
| program_name | varchar | 应用 |
| database_name | varchar | 数据库 |
| status | varchar | 状态 |
| open_transaction_count | int | 打开事务 |
| cpu_time | bigint | CPU |
| reads | bigint | 读 |
| writes | bigint | 写 |
| logical_reads | bigint | 逻辑读 |
| current_sql_hash | varchar | SQL hash |

## 11.3 request_snapshots

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 快照 ID |
| instance_id | uuid | 实例 ID |
| snapshot_time | timestamptz | 快照时间 |
| session_id | int | Session |
| request_id | int | Request |
| status | varchar | 状态 |
| command | varchar | 命令 |
| start_time | timestamptz | 开始时间 |
| duration_ms | bigint | 执行时长 |
| cpu_time_ms | bigint | CPU |
| reads | bigint | 读 |
| writes | bigint | 写 |
| logical_reads | bigint | 逻辑读 |
| wait_type | varchar | 等待类型 |
| wait_time_ms | bigint | 等待时间 |
| blocking_session_id | int | 阻塞源 |
| sql_hash | varchar | SQL hash |

## 11.4 blocking_snapshots

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 快照 ID |
| instance_id | uuid | 实例 ID |
| snapshot_time | timestamptz | 快照时间 |
| root_session_id | int | 根阻塞 |
| blocked_session_id | int | 被阻塞 |
| blocking_session_id | int | 直接阻塞源 |
| chain_depth | int | 链深度 |
| wait_type | varchar | 等待类型 |
| wait_time_ms | bigint | 等待时间 |
| resource_description | text | 锁资源 |

## 11.5 wait_snapshots

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 快照 ID |
| instance_id | uuid | 实例 ID |
| snapshot_time | timestamptz | 快照时间 |
| wait_type | varchar | 等待类型 |
| wait_category | varchar | 等待分类 |
| waiting_tasks_count | int | 等待任务数 |
| total_wait_time_ms | bigint | 等待总时长 |
| max_wait_time_ms | bigint | 最大等待时长 |

## 11.6 tempdb_snapshots

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 快照 ID |
| instance_id | uuid | 实例 ID |
| snapshot_time | timestamptz | 快照时间 |
| session_id | int | Session ID |
| user_objects_alloc_page_count | bigint | 用户对象分配页数 |
| internal_objects_alloc_page_count | bigint | 内部对象分配页数 |
| user_objects_dealloc_page_count | bigint | 用户对象释放页数 |
| internal_objects_dealloc_page_count | bigint | 内部对象释放页数 |
| tempdb_alloc_mb | numeric | 分配 MB |
| tempdb_current_mb | numeric | 当前净使用 MB |
| sql_hash | varchar | SQL hash |
| wait_type | varchar | 等待类型 |

## 11.7 sql_texts

| 字段 | 类型 | 说明 |
|---|---|---|
| sql_hash | varchar | SQL hash |
| normalized_hash | varchar | 归一化 hash |
| sql_text | text | SQL 文本 |
| first_seen_at | timestamptz | 首次出现 |
| last_seen_at | timestamptz | 最近出现 |

## 11.8 deadlock_events

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 事件 ID |
| instance_id | uuid | 实例 |
| occurred_at | timestamptz | 发生时间 |
| victim_session_id | int | Victim |
| database_name | varchar | 数据库 |
| deadlock_xml | text | XML |
| summary | jsonb | 摘要 |

## 11.9 kill_audits

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 审计 ID |
| operator | varchar | 操作人 |
| instance_id | uuid | 实例 |
| session_id | int | Session |
| reason | text | 原因 |
| before_snapshot | jsonb | 操作前快照 |
| result | varchar | 结果 |
| error_message | text | 错误 |
| created_at | timestamptz | 时间 |

## 12. API 范围

| API | 说明 |
|---|---|
| `GET /api/instances` | 实例列表 |
| `POST /api/instances` | 新增实例 |
| `PUT /api/instances/{id}` | 编辑实例 |
| `POST /api/instances/{id}/test` | 测试连接 |
| `GET /api/dashboard?instance_id=` | Dashboard 数据 |
| `GET /api/sessions?instance_id=` | 实时 Session |
| `GET /api/sessions/{session_id}` | Session 详情 |
| `GET /api/sqls?instance_id=` | 实时 SQL |
| `GET /api/sqls/{sql_hash}` | SQL 详情 |
| `GET /api/blocking?instance_id=` | 阻塞链 |
| `GET /api/waits?instance_id=` | Wait 分析 |
| `GET /api/resources/cpu?instance_id=` | CPU 分析 |
| `GET /api/resources/io?instance_id=` | IO 分析 |
| `GET /api/tempdb?instance_id=` | TempDB 分析 |
| `GET /api/deadlocks?instance_id=` | 死锁列表 |
| `GET /api/deadlocks/{id}` | 死锁详情 |
| `POST /api/kill` | Kill Session |
| `GET /api/replay?instance_id=&time=` | 历史回放 |
| `GET /api/audits/kills` | Kill 审计 |

## 13. 权限设计

## 13.1 角色

| 角色 | 权限 |
|---|---|
| Viewer | 只读查看 Dashboard 和基础指标 |
| Developer | 查看 SQL、Session、历史 |
| DBA | 查看全部数据并执行 Kill |
| Admin | 实例管理、用户管理、系统配置 |

## 13.2 权限矩阵

| 功能 | Viewer | Developer | DBA | Admin |
|---|---|---|---|---|
| 查看 Dashboard | 是 | 是 | 是 | 是 |
| 查看 Session | 是 | 是 | 是 | 是 |
| 查看完整 SQL | 否/脱敏 | 是 | 是 | 是 |
| 查看执行计划 | 否 | 是 | 是 | 是 |
| Kill Session | 否 | 否 | 是 | 是 |
| 查看审计 | 否 | 否 | 是 | 是 |
| 管理实例 | 否 | 否 | 否 | 是 |

## 14. 根因定位规则

### 初版规则

| 问题 | 判断条件 | 提示 |
|---|---|---|
| 阻塞严重 | 被阻塞 Session 数 >= 5 | 存在高影响阻塞链 |
| 根阻塞未提交事务 | root status = sleeping 且 open_transaction_count > 0 | 疑似应用未提交事务 |
| 锁等待 | wait_type like `LCK_M_%` | 当前瓶颈可能为锁等待 |
| CPU 压力 SQL | cpu_time / duration > 0.7 | SQL CPU 消耗较高 |
| IO 压力 SQL | logical_reads 或 reads 排名前列 | SQL IO 消耗较高 |
| 内存授予等待 | wait_type = `RESOURCE_SEMAPHORE` | 可能存在大查询等待内存 |
| 日志写等待 | wait_type = `WRITELOG` | 可能存在日志写入瓶颈 |
| 网络消费慢 | wait_type = `ASYNC_NETWORK_IO` | 可能客户端消费结果慢 |
| TempDB 压力 | TempDB top session 高且 PAGELATCH 等待 | 可能存在 TempDB 争用或大排序/Hash |

### 展示原则

根因提示只展示为“疑似原因”和“建议检查”，不使用绝对结论。

## 15. 非功能需求

## 15.1 实时性

1. 页面数据默认延迟小于 10 秒。
2. 手动刷新响应小于 3 秒。
3. 死锁事件在 10 秒内出现在事件列表。

## 15.2 性能

1. 单实例 1000 Session 内页面可正常展示。
2. Session 和 SQL 列表支持分页或虚拟滚动。
3. 后端 API P95 响应小于 1 秒。
4. Collector 采集失败不能阻塞 API。

## 15.3 可用性

1. 单实例采集失败不影响其他实例。
2. Collector 支持自动重试。
3. 服务重启后采集任务自动恢复。
4. 页面展示采集状态和错误原因。

## 15.4 安全

1. 数据库连接串加密存储。
2. 采集账号与 Kill 账号分离。
3. Kill 操作必须审计。
4. SQL 文本可配置脱敏。
5. 支持按角色控制 SQL 文本可见性。

## 15.5 数据保留

| 数据 | 默认保留 |
|---|---|
| 实时快照 | 7 天 |
| SQL 文本 | 7 天或按容量 |
| 死锁事件 | 30 天 |
| Kill 审计 | 180 天 |
| 聚合趋势 | 30 天 |

## 16. 直接部署要求

## 16.1 部署目录

```text
/opt/sqlmon/
  backend/
  frontend/
  venv/
  config/
    app.env
  logs/
  scripts/
    migrate.sh
    start-api.sh
    start-collector.sh
```

## 16.2 systemd 服务

| 服务 | 说明 |
|---|---|
| sqlmon-api.service | FastAPI API 服务 |
| sqlmon-collector.service | SQL Server 采集服务 |

## 16.3 Nginx

Nginx 职责：

1. 托管 Vue 构建后的静态文件。
2. 将 `/api` 反向代理到 FastAPI。
3. 配置访问日志和错误日志。

## 16.4 部署验收

1. 一台内网 Linux 服务器可以完成部署。
2. Nginx 可以访问前端页面。
3. FastAPI 可以连接 PostgreSQL。
4. Collector 可以连接至少 1 个 SQL Server 实例。
5. 服务重启后自动恢复。
6. 日志落盘到 `/opt/sqlmon/logs/`。

## 17. 里程碑计划

## 17.1 Milestone 1：实时基础能力

目标：先看见现场。

包含：

1. 实例管理。
2. Collector 基础采集。
3. Dashboard。
4. Session 列表。
5. SQL 列表。
6. 自动刷新。

## 17.2 Milestone 2：阻塞与处置闭环

目标：能定位并处理阻塞。

包含：

1. 阻塞链分析。
2. Session 详情。
3. 锁与事务信息。
4. Kill 操作。
5. Kill 审计。

## 17.3 Milestone 3：资源与根因分析

目标：能判断 CPU、IO、Wait、TempDB 方向。

包含：

1. Wait 分析。
2. CPU Top SQL。
3. IO Top SQL。
4. TempDB Top Session。
5. 基础根因提示。

## 17.4 Milestone 4：历史与事件

目标：能复盘。

包含：

1. 历史快照。
2. 历史回放。
3. 死锁捕获。
4. 事件列表。

## 18. MVP 总体验收标准

1. 可以接入至少 3 个 SQL Server 实例。
2. 可以在页面中切换实例。
3. 可以查看当前 Session 和正在执行 SQL。
4. 可以识别阻塞链并找到根阻塞 Session。
5. 可以查看 Wait 类型与关联 SQL。
6. 可以按 CPU、IO、耗时排序 SQL。
7. 可以查看 TempDB 使用最高 Session。
8. 可以捕获并查看死锁事件。
9. DBA 可以执行 Kill，且操作被审计。
10. 可以回放最近 24 小时历史快照。
11. 单实例采集失败不影响其他实例。
12. 默认刷新延迟不超过 10 秒。

## 19. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| DMV 采集开销过高 | 影响被监控实例 | 控制采集频率，避免默认采集执行计划 |
| SQL 文本敏感 | 泄露业务数据 | 支持脱敏和权限控制 |
| Kill 操作风险 | 影响业务事务 | 二次确认、原因必填、审计记录 |
| 历史数据增长过快 | PostgreSQL 存储压力 | 分区表、保留策略、定时清理 |
| 多实例采集失败相互影响 | 平台可用性下降 | 每实例独立采集任务和错误隔离 |
| 死锁捕获依赖权限 | 功能不可用 | 启动时检测权限并展示配置指引 |

## 20. 后续增强方向

1. WebSocket 或 SSE 实时推送。
2. 告警通知接入飞书、企业微信或 Webhook。
3. 自动诊断报告。
4. Query Store 集成。
5. SQL 指纹趋势分析。
6. 查询计划差异对比。
7. 文件级 IO 分析。
8. 更细粒度权限和操作审批。
