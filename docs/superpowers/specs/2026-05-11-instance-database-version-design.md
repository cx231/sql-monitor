# Instance Database Selection And Version Refresh Design

## Goal

Improve instance configuration so users can choose a database during instance creation and connection tests refresh SQL Server version metadata in the instance list.

## Current Context

- Instance management UI is in `frontend/src/views/InstancesView.vue`.
- Frontend instance API state is in `frontend/src/stores/instances.ts`.
- Backend instance routes are in `backend/app/api/routes/instances.py`.
- Backend instance behavior is in `backend/app/services/instance_service.py`.
- Current SQL-auth DSN creation always uses `Database={master}`.
- Current connection tests return version and current database but do not return database list and do not persist version updates for existing instances.

## User Experience

- The create-instance dialog includes a database selector.
- The selector defaults to `master` and initially offers only `master`.
- When the user clicks "测试连接", the backend uses host, port, username, and password to connect to SQL Server, then returns:
  - SQL Server version,
  - current database,
  - selectable database names.
- After a successful test, the selector options update from the returned database list.
- If `master` is present, it remains the default unless the user explicitly chooses another database.
- If the user already selected a database and it still exists in the returned list, keep that selection.
- Saving the instance uses the selected database in the generated collect DSN and persists `database_name`.

## Existing Instance Test Behavior

- Clicking "测试" in the instance list tests the stored collect DSN.
- On success, the backend updates the instance row with the returned SQL Server version.
- The backend also updates `database_name` from the test result when it is available.
- The frontend updates the row in-place after a successful existing-instance test, so the list reflects the latest version without a manual refresh.
- Failed tests do not overwrite stored version or database metadata.

## Backend Design

- Extend `InstanceConnectionTestRequest` with `database_name`, defaulting to `master`.
- Extend `InstanceConnectionTestOut` with `databases: list[str]` and `instance: InstanceOut | None`.
- Update `build_sql_auth_connection_string()` to accept a `database_name` argument.
- Update new-connection tests to use the requested database in the DSN.
- Query SQL Server with one batch that returns version, current database, and database names from `sys.databases`.
- Filter database rows to online databases by using `state_desc = 'ONLINE'` and order by database name.
- Existing-instance test persists metadata only when the connection test succeeds.

## Frontend Design

- Extend `InstanceConnectionForm` with `database_name`.
- Extend test result type with `databases` and optional `instance`.
- Add `databaseOptions` state in `InstancesView.vue`, initialized to `['master']`.
- Add an Element Plus select for database in the create dialog.
- Test-new-connection updates database options on success.
- Save sends the selected database and SQL Server version.
- Existing test uses `result.instance` to update the store row when present.

## Error Handling

- If database list is empty or missing, keep `master` as the only option.
- If connection test fails, keep the previous database selector state.
- If existing-instance test fails, do not update the instance row.

## Testing

- Backend unit tests cover:
  - SQL-auth DSN includes requested database,
  - new connection test returns database list,
  - existing connection test persists SQL Server version and database name on success,
  - existing connection test does not persist metadata on failure.
- Frontend build verifies TypeScript and Vue template changes.
- Browser verification checks the create dialog database selector default and interaction surface.

## Out Of Scope

- Editing existing instance credentials.
- Backend user-specific preferences.
- Validating database permissions beyond the connection test.
