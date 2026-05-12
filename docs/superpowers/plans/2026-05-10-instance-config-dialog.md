# Instance Config Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add instance create/delete/test workflows to the instance settings UI, including a layered SQL-auth add dialog.

**Architecture:** Backend extends the existing instances route and service with DSN building, connection testing, and deletion. Frontend keeps the instance page as the owner of the dialog and row actions, using the existing Pinia store and Axios client. Tests focus on backend behavior and route permissions; frontend is verified through typecheck/build and browser inspection.

**Tech Stack:** FastAPI, SQLAlchemy async, pyodbc-backed SQL Server client, Vue 3, Element Plus, Pinia, vxe-table.

---

### Task 1: Backend Instance Test and Delete Services

**Files:**
- Modify: `backend/app/schemas/instances.py`
- Modify: `backend/app/services/instance_service.py`
- Test: `backend/tests/unit/test_instance_service.py`

- [ ] **Step 1: Write failing tests**

Add tests for DSN construction, sanitized connection test success/failure, stored-DSN testing, and delete behavior in `backend/tests/unit/test_instance_service.py`.

Run: `cd backend && pytest tests/unit/test_instance_service.py -q`
Expected: FAIL because the new service functions and schemas do not exist.

- [ ] **Step 2: Implement schemas and services**

Add `InstanceConnectionTestRequest` and `InstanceConnectionTestOut`. Implement:

```python
build_sql_auth_connection_string(host, port, username, password)
test_new_instance_connection(data, client_factory=SqlServerClient)
test_existing_instance_connection(session, instance_id, client_factory=SqlServerClient)
delete_instance(session, instance_id)
```

Deletion removes `InstanceCollectStatus` first, then `Instance`.

- [ ] **Step 3: Verify backend unit tests**

Run: `cd backend && pytest tests/unit/test_instance_service.py -q`
Expected: PASS.

### Task 2: Backend Routes

**Files:**
- Modify: `backend/app/api/routes/instances.py`
- Test: `backend/tests/unit/test_instance_service.py`

- [ ] **Step 1: Write failing route permission and 404 tests**

Add tests for:

```text
DELETE /api/instances/{id} requires admin
POST /api/instances/test-connection requires admin
POST /api/instances/{id}/test-connection requires admin
DELETE /api/instances/{id} returns 404 for missing instance
POST /api/instances/{id}/test-connection returns 404 for missing instance
```

Run: `cd backend && pytest tests/unit/test_instance_service.py -q`
Expected: FAIL because routes do not exist.

- [ ] **Step 2: Implement routes**

Add admin-only routes for delete, ad-hoc test, and existing-instance test. Existing-instance test returns 404 when the service returns `None`.

- [ ] **Step 3: Verify route tests**

Run: `cd backend && pytest tests/unit/test_instance_service.py -q`
Expected: PASS.

### Task 3: Frontend Instance Store Types and Actions

**Files:**
- Modify: `frontend/src/stores/instances.ts`

- [ ] **Step 1: Add typed request/response models and actions**

Add:

```ts
export interface InstanceConnectionForm {
  name: string;
  host: string;
  port: number;
  username: string;
  password: string;
}

export interface InstanceConnectionTestResult {
  success: boolean;
  sqlserver_version: string | null;
  database_name: string | null;
  error_message: string | null;
}
```

Add actions for `createInstanceFromForm`, `testNewConnection`, `testExistingConnection`, and `deleteInstance`.

- [ ] **Step 2: Verify TypeScript**

Run: `cd frontend && npm run build`
Expected: may still fail until Task 4 uses the new actions correctly; no syntax errors in the store.

### Task 4: Frontend Layered Dialog and Row Actions

**Files:**
- Modify: `frontend/src/views/InstancesView.vue`

- [ ] **Step 1: Implement UI**

Add primary "新增实例" button, row-level "测试" and "删除" actions, and a layered Element Plus dialog with:

```text
Header: 新增 SQL Server 实例 + SQL 认证 badge
基础连接: 实例名称, IP 地址, 端口
SQL 认证: 用户, 密码
Side panel: connection test result and password note
Footer: 测试连接, 取消, 保存
```

- [ ] **Step 2: Implement form behavior**

Validate required fields and port range. Test connection before save when requested. Save builds via store action, refreshes list, and closes dialog. Delete uses `ElMessageBox.confirm`.

- [ ] **Step 3: Verify frontend build**

Run: `cd frontend && npm run build`
Expected: PASS.

### Task 5: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend tests**

Run: `cd backend && pytest -q`
Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 3: Browser inspect**

Run the dev server if needed and inspect the instance settings page. Confirm the layered dialog layout, row test action, and delete confirmation render without overlap.
