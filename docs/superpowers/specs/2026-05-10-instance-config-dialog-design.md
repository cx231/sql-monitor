# Instance Config Dialog Design

## Goal

Adjust the instance configuration screen so an admin can add, delete, and test SQL Server instances from the UI. Adding an instance opens a layered dialog with the required SQL authentication fields and an in-dialog connection test.

## Scope

This change covers:

1. Add an "新增实例" action on the instance settings page.
2. Add per-instance "测试" and "删除" actions in the instance table.
3. Open a layered add-instance dialog with these required fields:
   - 实例名称
   - IP 地址
   - 端口
   - 用户 (SQL 认证)
   - 密码
4. Allow testing the connection before saving.
5. Save the instance only after the API receives the add request.
6. Delete an instance only after a confirmation dialog.

This change does not add instance editing, Windows authentication, approval workflow, or alerting.

## UX Design

The instance settings page remains a dense operational page rather than a marketing-style screen. The toolbar keeps the global instance selector, refresh button, and a new primary add button.

The add dialog uses clear visual hierarchy:

1. Header area: title, short instruction, and SQL authentication badge.
2. Main form area: "基础连接" section for name, IP, and port.
3. Authentication area: "SQL 认证" section for username and password.
4. Side panel: connection test result and password handling note.
5. Footer area: test, cancel, and save actions.

The dialog should avoid adding extra required fields. Backend defaults cover environment, collection interval, retention, status, and database name.

## Backend Design

The existing `POST /api/instances` endpoint already creates instances from a DSN. The UI will send a generated SQL Server ODBC connection string as `collect_dsn`.

Add these API capabilities:

1. `DELETE /api/instances/{instance_id}` for admin-only deletion.
2. `POST /api/instances/test-connection` for admin-only ad-hoc connection testing from form fields.
3. `POST /api/instances/{instance_id}/test-connection` for admin-only testing of an existing instance's stored collection DSN.

Connection testing should run a small SQL query through the existing SQL Server client:

```sql
SELECT
  @@VERSION AS sqlserver_version,
  DB_NAME() AS database_name
```

The API response must return whether the test succeeded, plus version/database details or an error message. It must not return usernames, passwords, or DSNs.

## Data Flow

For a new instance:

1. User fills the dialog.
2. Frontend validates required fields and port range.
3. User clicks "测试连接".
4. Frontend sends host, port, username, and password to `POST /api/instances/test-connection`.
5. Backend builds a SQL Server ODBC DSN, runs the lightweight query, and returns a sanitized result.
6. User clicks "保存".
7. Frontend sends `POST /api/instances` with the generated `collect_dsn`; password is never displayed after save.
8. Frontend refreshes the instance list and closes the dialog.

For an existing instance:

1. User clicks row-level "测试".
2. Frontend sends `POST /api/instances/{id}/test-connection`.
3. Backend decrypts the stored collection DSN, tests it, and returns a sanitized result.
4. Frontend shows success or failure feedback.

For deletion:

1. User clicks row-level "删除".
2. Frontend shows a confirmation dialog with the instance name.
3. Frontend sends `DELETE /api/instances/{id}` after confirmation.
4. Backend deletes the instance and associated collection status in the same transaction.
5. Frontend refreshes the list and clears the selected instance if needed.

## Error Handling

1. Required form fields show inline validation errors.
2. Invalid port is rejected client-side and server-side.
3. Connection failures return `success: false` with a safe error message.
4. Missing instance IDs return 404.
5. Non-admin users keep receiving 403 on mutation and test endpoints.

## Testing

Backend tests should cover:

1. Building a DSN from SQL authentication fields.
2. Successful new-connection test without exposing secrets.
3. Failed connection test returns a sanitized failure response.
4. Existing-instance connection test uses stored encrypted DSN.
5. Deletion removes the instance and its collect status.
6. Delete and test routes require admin role.

Frontend verification should cover:

1. Type checking and production build.
2. Manual browser check of the instance settings page, add dialog hierarchy, test action, and delete confirmation.
