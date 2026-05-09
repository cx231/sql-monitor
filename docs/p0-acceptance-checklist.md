# P0 验收清单

## 验收目标

确认 P0 端到端闭环可以在无真实 PostgreSQL 的条件下完成验收，核心包括采集结果、仪表盘、会话列表、SQL 列表、阻塞链和回放能力。

## 种子数据要求

- 两个实例
- 一个实例采集成功，至少有 1 个 frame
- 一个实例采集失败，没有可用 frame
- 1 个 frame
- 3 个 session
- 2 个 request
- 1 个 blocking edge
- 1 个 wait aggregate

## 验收步骤

- [ ] 访问成功实例的 Dashboard，确认计数正确
- [ ] 访问成功实例的 Session 列表，确认返回 3 行
- [ ] 访问成功实例的 SQL 列表，确认返回 2 行
- [ ] 访问成功实例的 Blocking API，确认只有 1 条根阻塞链
- [ ] 访问成功实例的 Replay API，确认返回目标时间之前最近的 frame
- [ ] 访问失败实例的 Dashboard，确认返回最新 frame 缺失
- [ ] 执行 `cd backend && python3 -m pytest -v`
- [ ] 执行 `cd frontend && npm run build`

## 完成标准

- 验收清单文件已存在且为中文
- 后端集成验收测试通过
- 前端构建通过
