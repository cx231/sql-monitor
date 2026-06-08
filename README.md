# SQLMon

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)
![Vue](https://img.shields.io/badge/Vue-3.x-42B883)
![License](https://img.shields.io/badge/License-MIT-blue)

SQLMon 是一个面向内网使用的 SQL Server 实时会话监控平台，帮助 DBA、后端研发和运维/SRE 在同一页面内完成实例观察、会话分析、SQL 诊断、阻塞定位、Kill 处置和历史回放。

## 项目简介

SQL Server 线上问题常常依赖“现场”：当前 Session、正在执行的 SQL、等待类型、阻塞链、资源消耗和处置动作。如果没有持续采集，这些信息很容易在事后丢失。

SQLMon 通过独立的 Collector 进程周期采集 SQL Server DMV 数据，并将快照写入 PostgreSQL；FastAPI 后端提供查询、鉴权、实例管理和 Kill 审计接口；Vue 前端提供实时监控和排障操作界面。

```text
Browser
  |
  | HTTP / Vite proxy / Nginx
  v
Vue Frontend
  |
  | /api
  v
FastAPI Backend
  |
  | SQLAlchemy async
  v
PostgreSQL

Collector Worker
  |
  | pyodbc + Microsoft ODBC Driver 18
  v
SQL Server Instances
```

术语简释：

- **DMV**：SQL Server Dynamic Management Views，动态管理视图，用于查询当前连接、请求、等待、锁和资源状态。
- **Collector**：后台采集器，按固定间隔连接 SQL Server 并保存监控快照。
- **Snapshot**：某一时刻的监控数据快照，用于实时展示和历史回放。

## 功能特点

- **多实例管理**：新增、编辑、禁用和切换 SQL Server 实例，支持连接测试和采集状态展示。
- **实时 Dashboard**：展示连接数、活动请求、阻塞、等待、CPU/内存/网络趋势和 Top SQL。
- **会话与 SQL 分析**：按状态、阻塞、事务和资源消耗筛选 Session，查看完整 SQL 文本和执行指标。
- **阻塞链定位与 Kill 审计**：识别根阻塞 Session，支持安全 Kill 确认、权限校验和审计记录。
- **历史回放与索引治理**：按时间回放历史快照，查看缺失索引建议和索引碎片维护入口。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite、TypeScript、Element Plus、Pinia、vxe-table、ECharts |
| 后端 | Python 3.11+、FastAPI、Pydantic Settings、PyJWT、bcrypt |
| 数据访问 | SQLAlchemy 2.x async、asyncpg、Alembic、pyodbc |
| 存储 | PostgreSQL |
| 采集调度 | APScheduler、独立 Collector 进程 |
| 部署 | Linux、Nginx、systemd |

## 安装与运行

### 环境要求

推荐开发环境：

- macOS 或 Linux
- Python 3.11+
- Node.js 18+ 和 npm
- PostgreSQL 14+
- Microsoft ODBC Driver 18 for SQL Server

生产环境推荐部署在内网 Linux 服务器，并使用 Nginx + systemd 管理前端静态资源、API 服务和 Collector 服务。

### 1. 克隆并进入项目

```bash
git clone https://github.com/cx231/sql-monitor.git sqlmon
cd sqlmon
```

如果已经在当前仓库工作树中：

```bash
cd /Users/chenxuan/sql/.worktrees/sqlmon-p0
```

### 2. 准备 PostgreSQL

创建数据库和用户，或在 `backend/.env` 中配置自己的连接串。以下示例会创建默认连接串使用的 `sqlmon` 用户和数据库：

```bash
psql postgres -c "CREATE USER sqlmon WITH PASSWORD 'password';"
psql postgres -c "CREATE DATABASE sqlmon OWNER sqlmon;"
```

`backend/.env` 示例：

```env
SQLMON_ENV=dev
SQLMON_SECRET_KEY=dev-secret-key
SQLMON_DATABASE_URL=postgresql+asyncpg://sqlmon:password@127.0.0.1:5432/sqlmon
SQLMON_API_HOST=127.0.0.1
SQLMON_API_PORT=8000
```

生产环境必须把 `SQLMON_SECRET_KEY` 设置为不少于 32 个字符的安全随机字符串。完整变量示例见 [`deploy/env/app.env.example`](deploy/env/app.env.example)。

### 3. 启动后端 API

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

迁移完成后会初始化默认管理员：

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `Admin@2026` | `admin` |

生产环境上线后请立即修改默认密码。

### 4. 启动 Collector

Collector 负责周期采集 SQL Server 实例数据。首次体验可以先启动 API 和前端，再在页面中添加实例。

```bash
cd backend
source .venv/bin/activate
python -m app.collector.main --interval-seconds 5
```

只采集一次可用于排查连接或采集问题：

```bash
python -m app.collector.main --once
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

| 服务 | 地址 |
| --- | --- |
| 前端 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000/api |
| 健康检查 | http://127.0.0.1:8000/api/health |

Vite 已将 `/api` 代理到 `http://localhost:8000`。

## 使用示例

### 检查 API 是否正常

```bash
curl http://127.0.0.1:8000/api/health
```

预期输出：

```json
{"status":"ok"}
```

### 登录并开始监控

1. 打开 http://127.0.0.1:5173/login。
2. 使用默认管理员 `admin` / `Admin@2026` 登录。
3. 进入“实例设置”，添加 SQL Server 实例并执行连接测试。
4. 启动 Collector。
5. 在“仪表盘”“会话监控”“SQL 分析”或“阻塞分析”中查看实时数据。

更完整的页面说明和排障流程见 [`docs/sqlmon-user-guide.md`](docs/sqlmon-user-guide.md)。

### 常用检查命令

后端测试：

```bash
cd backend
python3 -m pytest -v
```

前端构建：

```bash
cd frontend
npm run build
```

数据库迁移：

```bash
cd backend
alembic upgrade head
```

生产部署脚本入口：

```bash
APP_HOME=/opt/sqlmon deploy/scripts/migrate.sh
APP_HOME=/opt/sqlmon deploy/scripts/start-api.sh
APP_HOME=/opt/sqlmon deploy/scripts/start-collector.sh
```

## 项目结构

```text
.
├── backend/                 # FastAPI API、业务服务、Collector 和 Alembic 迁移
│   ├── app/api/routes/      # REST API 路由
│   ├── app/collector/       # SQL Server 采集器
│   ├── app/db/              # PostgreSQL 连接、模型和迁移
│   └── tests/               # 后端单元测试与集成测试
├── frontend/                # Vue 3 + Vite 前端工程
│   ├── src/views/           # Dashboard、Session、SQL、阻塞、回放等页面
│   ├── src/components/      # 通用业务组件
│   └── src/api/             # API 客户端和类型定义
├── deploy/                  # Nginx、systemd、启动脚本和环境变量示例
└── docs/                    # PRD、技术设计、用户指南和验收清单
```

## 贡献与社区

欢迎通过 Issue、Pull Request 或内部评审流程参与改进。

建议流程：

1. 先阅读 [`docs/sql-server-realtime-session-monitor-prd.md`](docs/sql-server-realtime-session-monitor-prd.md) 和 [`docs/sql-server-realtime-session-monitor-tech-design.md`](docs/sql-server-realtime-session-monitor-tech-design.md)。
2. 为每个变更创建独立分支，并保持提交范围清晰。
3. 后端变更请补充或更新 `backend/tests/` 中的测试。
4. 前端变更请至少执行 `npm run build`，确保 TypeScript 类型检查和 Vite 构建通过。
5. 提交 PR 前运行：

```bash
cd backend && python3 -m pytest -v
cd frontend && npm run build
```

报告问题时请尽量包含：

- SQLMon 版本或提交号
- 操作系统和部署方式
- PostgreSQL、SQL Server、ODBC Driver 版本
- 复现步骤、错误日志和截图

## 许可证

本项目采用 MIT License。你可以自由使用、复制、修改和分发本项目，但需保留原始版权声明和许可证文本。
