# Instance Database Selection And Version Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add database selection to instance creation and refresh SQL Server version metadata when connection tests succeed.

**Architecture:** Extend existing instance schemas and service functions rather than adding new endpoints. The backend returns database lists and updated instance data from connection tests; the frontend keeps database selection state in the instance dialog and updates Pinia store rows in-place.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy async session patterns, Vue 3, Pinia, Element Plus, Vite.

---

### Task 1: Backend Tests For Connection Metadata

**Files:**
- Modify: `backend/tests/unit/test_instance_service.py`

- [ ] **Step 1: Add failing DSN test**

Update `test_build_sql_auth_connection_string_uses_sql_auth_fields` to pass `database_name="Orders"` and assert `Database={Orders}`.

- [ ] **Step 2: Add failing new-test database list assertion**

Update `test_new_instance_connection_test_returns_sanitized_success` fake rows to include database rows and assert:

```python
assert result.databases == ["master", "Orders"]
```

- [ ] **Step 3: Add failing existing-test persistence test**

Add a test that uses a fake session with `commit()` and `refresh()` tracking. The fake SQL client returns a SQL Server version, current database, and database list. Assert the stored `Instance.sqlserver_version` and `database_name` change after a successful existing connection test.

- [ ] **Step 4: Add failing existing-test failure preservation test**

Add a test where the fake SQL client raises. Assert `success is False`, and the stored `Instance.sqlserver_version` and `database_name` remain unchanged.

- [ ] **Step 5: Run targeted backend tests**

Run: `cd backend && python3 -m pytest tests/unit/test_instance_service.py -q`

Expected: tests fail because backend behavior is not implemented yet.

### Task 2: Backend Implementation

**Files:**
- Modify: `backend/app/schemas/instances.py`
- Modify: `backend/app/services/instance_service.py`
- Modify: `backend/app/api/routes/instances.py`

- [ ] **Step 1: Extend schemas**

Add `database_name: Optional[str] = Field(default="master", max_length=128)` to `InstanceConnectionTestRequest`.

Add `databases: list[str] = Field(default_factory=list)` and `instance: Optional[InstanceOut] = None` to `InstanceConnectionTestOut`.

- [ ] **Step 2: Update DSN builder**

Change `build_sql_auth_connection_string()` to accept `database_name: str = "master"` and emit `Database={...}` using that value.

- [ ] **Step 3: Add database list SQL**

Change the connection test SQL to return a result shape the service can parse, for example:

```sql
SELECT
  @@VERSION AS sqlserver_version,
  DB_NAME() AS database_name,
  CAST(NULL AS sysname) AS available_database_name
UNION ALL
SELECT
  CAST(NULL AS nvarchar(max)) AS sqlserver_version,
  CAST(NULL AS sysname) AS database_name,
  name AS available_database_name
FROM sys.databases
WHERE state_desc = 'ONLINE'
ORDER BY available_database_name;
```

- [ ] **Step 4: Parse test rows**

Return the first non-empty version/current database and all `available_database_name` values. If no database names are returned, use `[database_name or "master"]`.

- [ ] **Step 5: Persist existing metadata on success**

In `test_existing_instance_connection()`, after a successful result:

```python
if result.success:
    if result.sqlserver_version:
        instance.sqlserver_version = result.sqlserver_version
    if result.database_name:
        instance.database_name = result.database_name
    await session.commit()
    await session.refresh(instance)
    result.instance = _to_instance_out(instance)
```

- [ ] **Step 6: Run targeted backend tests**

Run: `cd backend && python3 -m pytest tests/unit/test_instance_service.py -q`

Expected: targeted tests pass.

### Task 3: Frontend Store

**Files:**
- Modify: `frontend/src/stores/instances.ts`

- [ ] **Step 1: Extend types**

Add `database_name: string` to `InstanceConnectionForm`. Add `databases: string[]` and `instance: InstanceItem | null` to `InstanceConnectionTestResult`.

- [ ] **Step 2: Update DSN builder**

Use `form.database_name || 'master'` for the DSN database segment.

- [ ] **Step 3: Update create payload**

Send `database_name` and `sqlserver_version` when creating from the form. The version will be passed from the dialog after a successful test.

- [ ] **Step 4: Update existing test action**

When `testExistingConnection()` receives `data.instance`, replace that row in `items`.

- [ ] **Step 5: Run frontend build**

Run: `cd frontend && npm run build`

Expected: build fails until `InstancesView.vue` is updated, then passes after Task 4.

### Task 4: Frontend Dialog UI

**Files:**
- Modify: `frontend/src/views/InstancesView.vue`

- [ ] **Step 1: Add database form field**

Initialize `createForm.database_name = "master"` and add validation.

- [ ] **Step 2: Add database options state**

Add `databaseOptions = ref(["master"])` and a helper that normalizes returned database names while keeping `master` first if present.

- [ ] **Step 3: Add select to dialog**

Add an `el-form-item` labeled `数据库` with `el-select`, placed in the basic connection section.

- [ ] **Step 4: Update new test handler**

On successful test, update database options from `result.databases`. Keep current selected DB if available, otherwise use `master` if present, otherwise first returned database.

- [ ] **Step 5: Update save handler**

Pass the selected database and successful test version to `createInstanceFromForm`.

- [ ] **Step 6: Update existing test handler**

After success, rely on the store-updated row and show a success message that includes version when returned.

- [ ] **Step 7: Run frontend build**

Run: `cd frontend && npm run build`

Expected: build passes.

### Task 5: Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run backend tests**

Run: `cd backend && python3 -m pytest -q`

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

Expected: build passes with only existing Vite warnings.

- [ ] **Step 3: Browser check**

Start Vite, open instance settings, and verify the create dialog includes database selector defaulting to `master`.

- [ ] **Step 4: Whitespace and status checks**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; status contains intended changes plus previous uncommitted requested work.
