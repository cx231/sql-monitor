# Instance Edit And Auto Test Design

## Goal

Improve the instance configuration screen with complete create/edit fields, fix deletion behavior, and add periodic database status testing.

## Current Context

- The instance page is `frontend/src/views/InstancesView.vue`.
- Instance API state is `frontend/src/stores/instances.ts`.
- Backend instance routes and service already support create, update, delete, new connection test, and existing connection test.
- The current delete path physically deletes the instance and only removes `instance_collect_status`; this can fail when historical snapshot tables reference the instance.
- Existing auto refresh controls elsewhere use `5/10/30/60` second intervals.

## Dialog Layout

- Use one dialog for both create and edit.
- Dialog title changes between `新增 SQL Server 实例` and `编辑 SQL Server 实例`.
- `基础连接` contains:
  - instance name,
  - IP address,
  - port.
- `SQL 认证` contains:
  - SQL user,
  - password,
  - database selector.
- `采集策略` contains:
  - collect interval seconds,
  - retention days.

## Create Behavior

- Create defaults:
  - port: `1433`,
  - database: `master`,
  - collect interval: `5`,
  - retention days: `7`.
- Saving create builds a collect DSN from host, port, selected database, user, and password.
- If a successful connection test returned SQL Server version, save it with the instance.

## Edit Behavior

- Row actions include `编辑`, `测试`, and `删除`.
- Edit loads existing instance values into the dialog.
- Editable fields:
  - name,
  - host,
  - port,
  - database,
  - collect interval seconds,
  - retention days,
  - SQL user/password for rebuilding the collect DSN.
- SQL user/password are optional in edit mode.
- If edit user/password are blank, save metadata only and keep the existing encrypted collect DSN.
- If edit user/password are filled, rebuild collect DSN with the current database and connection fields.
- Editing uses `PUT /api/instances/{id}` and updates the frontend row immediately.

## Delete Behavior

- Delete becomes a soft delete.
- Clicking delete sets the instance `status` to `disabled` and removes it from the active frontend list.
- Backend `DELETE /api/instances/{id}` no longer physically deletes the instance row or historical snapshot references.
- `GET /api/instances` hides disabled instances so refresh does not bring deleted rows back.
- Historical monitoring data remains intact.

## Connection Testing

- Row `测试` keeps the existing behavior of testing stored collect DSN.
- On success, backend updates:
  - `status = online`,
  - SQL Server version when returned,
  - database name when returned.
- On failure, backend updates:
  - `status = offline`,
  - no version/database overwrite.
- The test response includes the updated instance, and the frontend replaces the row in-place.

## Automatic Status Testing

- Instance page toolbar adds a compact auto-test control to the left of the manual `刷新` button.
- Control includes:
  - switch,
  - interval selector,
  - manual `测试状态` button.
- Interval options are `5/10/30/60/120/300 秒`.
- When enabled, the page periodically tests visible instances one-by-one by calling the existing row test API.
- If a previous auto-test cycle is still running, the next cycle is skipped.
- Manual `测试状态` runs the same cycle immediately.

## Testing

- Backend tests cover:
  - delete sets status to disabled rather than physical deletion,
  - list hides disabled instances,
  - existing connection test updates status online on success,
  - existing connection test updates status offline on failure,
  - update preserves existing DSN when no replacement DSN is provided.
- Frontend build verifies TypeScript and Vue changes.
- Browser verification checks:
  - database field is under SQL authentication,
  - collect interval and retention fields are present,
  - edit button opens edit dialog,
  - auto-test interval includes `120` and `300` seconds,
  - layout has no horizontal overflow.

## Out Of Scope

- Physically deleting historical snapshot data.
- Background server-side schedulers for status testing.
- Editing kill DSN.
