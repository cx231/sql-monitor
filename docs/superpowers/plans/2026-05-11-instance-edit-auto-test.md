# Instance Edit And Auto Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add edit support, collect policy fields, reliable soft delete, and periodic status testing to the instance configuration screen.

**Architecture:** Keep the current FastAPI instance endpoints and Vue instance page, extending existing service functions and Pinia actions. Use soft delete by setting `status=disabled`, and implement periodic testing on the frontend by reusing the existing existing-instance test API.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, Vue 3, Pinia, Element Plus, Vite.

---

### Task 1: Backend Tests

**Files:**
- Modify: `backend/tests/unit/test_instance_service.py`

- [ ] **Step 1: Add list filter test**

Add a test where fake query returns one `online` and one `disabled` instance. Assert `list_instances()` returns only the non-disabled instance.

- [ ] **Step 2: Add soft delete test**

Update delete tests so `delete_instance()` sets `instance.status == "disabled"`, commits, refreshes, and does not call `delete()` on historical-linked rows.

- [ ] **Step 3: Add connection status tests**

Update existing connection test expectations:

- success sets `instance.status == "online"`,
- failure sets `instance.status == "offline"`,
- failure does not overwrite version/database.

- [ ] **Step 4: Run targeted tests**

Run: `cd backend && python3 -m pytest tests/unit/test_instance_service.py -q`

Expected: tests fail until service behavior is updated.

### Task 2: Backend Implementation

**Files:**
- Modify: `backend/app/services/instance_service.py`

- [ ] **Step 1: Hide disabled instances**

Change `list_instances()` to filter `Instance.status != "disabled"`.

- [ ] **Step 2: Update connection test status**

In `test_existing_instance_connection()`:

- success sets `status = "online"`,
- failure sets `status = "offline"`, commits, refreshes, and returns updated `instance`.

- [ ] **Step 3: Implement soft delete**

Change `delete_instance()` to:

```python
instance.status = "disabled"
await session.commit()
await session.refresh(instance)
return True
```

- [ ] **Step 4: Run targeted tests**

Run: `cd backend && python3 -m pytest tests/unit/test_instance_service.py -q`

Expected: targeted tests pass.

### Task 3: Frontend Store

**Files:**
- Modify: `frontend/src/stores/instances.ts`

- [ ] **Step 1: Extend form type**

Add:

```ts
collect_interval_seconds: number;
retention_days: number;
```

- [ ] **Step 2: Add update action**

Add `updateInstanceFromForm(instanceId, form, options)` that sends `PUT /instances/{id}`. If user/password are present, rebuild `collect_dsn`; otherwise omit it.

- [ ] **Step 3: Update create payload**

Include `collect_interval_seconds` and `retention_days`.

- [ ] **Step 4: Update delete action**

After `DELETE`, remove the row locally as today. Backend now performs soft delete.

### Task 4: Instance Dialog UI

**Files:**
- Modify: `frontend/src/views/InstancesView.vue`

- [ ] **Step 1: Add dialog mode**

Add `dialogMode: "create" | "edit"` and `editingInstance`.

- [ ] **Step 2: Move database field**

Move database select from `基础连接` to `SQL 认证`.

- [ ] **Step 3: Add collect policy section**

Add `采集策略` section with:

- collect interval number input,
- retention days number input.

- [ ] **Step 4: Add edit action**

Add row `编辑` button. On click, populate the form from the row. Leave user/password blank.

- [ ] **Step 5: Save by mode**

Create mode calls create action. Edit mode calls update action. Close and refresh/update local row after success.

- [ ] **Step 6: Update validation**

In edit mode, user/password are optional. In create mode, user/password are required.

### Task 5: Auto Status Test UI

**Files:**
- Modify: `frontend/src/views/InstancesView.vue`

- [ ] **Step 1: Add toolbar control**

Add switch, interval select, and manual `测试状态` button to the left of `刷新`.

Interval options: `5/10/30/60/120/300 秒`.

- [ ] **Step 2: Add timer behavior**

Use `setInterval` and `onBeforeUnmount`. When enabled, call `testAllInstances()`.

- [ ] **Step 3: Avoid overlap**

Track `testingAllInstances`. If already true, skip the next tick.

- [ ] **Step 4: Test all visible instances**

Loop through `store.items` and call `store.testExistingConnection(item.id)` sequentially.

### Task 6: Verification

**Files:**
- Verify only.

- [ ] **Step 1: Backend tests**

Run: `cd backend && python3 -m pytest -q`

Expected: all backend tests pass.

- [ ] **Step 2: Frontend build**

Run: `cd frontend && npm run build`

Expected: build passes with only existing Vite warnings.

- [ ] **Step 3: Browser check**

Open instance settings and verify:

- create dialog has database under SQL auth,
- collect interval and retention days are present,
- row actions include edit/test/delete,
- toolbar auto-test options include `120 秒` and `300 秒`,
- no horizontal overflow.

- [ ] **Step 4: Final checks**

Run:

```bash
git diff --check
git status --short
```
