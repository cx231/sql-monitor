# User Management Design

## Goal

Add an admin-only user management page that supports creating users, editing user metadata, disabling users, and resetting passwords.

## Roles And Permissions

The feature follows the product permission matrix:

| Role | Permissions |
|---|---|
| viewer | Read-only dashboard and basic metrics |
| developer | View sessions, SQL, replay history, and full SQL text |
| dba | View all monitoring data, kill sessions, and view audits |
| admin | Manage instances, users, and system settings |

Permissions are role-based. The first version does not add per-permission checkboxes or a separate permissions table.

## Backend

Add admin-only `/api/users` endpoints:

- `GET /api/users` lists users.
- `POST /api/users` creates an active user with a hashed password.
- `PUT /api/users/{user_id}` edits `display_name`, `role`, and `status`.
- `POST /api/users/{user_id}/disable` disables a user instead of physically deleting it.
- `POST /api/users/{user_id}/reset-password` sets a new hashed password.

All user management endpoints require the `admin` role. A user cannot disable their own account. Login already rejects disabled users through the existing authentication service.

## Frontend

Add a `用户管理` item to the left navigation with a user-management icon. The page uses the existing operational layout: toolbar, table, and dialogs. Row actions are `编辑`, `重置密码`, and `禁用`; no `删除` button is shown.

The page displays username, display name, role, status, created time, and updated time. Role labels include the permissions summary so administrators understand what each role grants.

## Validation

Backend unit tests cover admin-only access, user creation, update, disable, password reset, self-disable rejection, and disabled login rejection. Frontend check script verifies the route, sidebar navigation, visible `禁用` action, and absence of a `删除` action on the user management page.
