# Sidebar Icons And Collapse Design

## Goal

Add scene-appropriate icons to the left navigation and allow the sidebar to collapse into an icon-only rail. The collapsed state must persist after page refresh.

## Current Context

- The main application shell is implemented in `frontend/src/layouts/MainLayout.vue`.
- Navigation is currently a flat Element Plus `el-menu` with text-only `el-menu-item` entries.
- The app already depends on Element Plus and uses `@element-plus/icons-vue` in multiple frontend files.
- Theme variables are defined globally and already support light and dark modes.

## User Experience

- The expanded sidebar remains close to the current 220px width and shows brand text, icons, and menu labels.
- The collapsed sidebar is about 64px wide and shows only icons.
- A compact toggle button is placed in the sidebar brand area.
- The active route remains visually clear in both expanded and collapsed states.
- Menu items expose text labels through Element Plus menu item title behavior when collapsed.
- The collapse setting is stored in `localStorage` and restored when the layout mounts.

## Navigation Icon Mapping

- `仪表盘`: `DataLine`
- `会话监控`: `Connection`
- `SQL 分析`: `Document`
- `阻塞分析`: `Warning`
- `回放分析`: `VideoPlay`
- `实例设置`: `Setting`

These icons match the monitoring, connection, SQL document, warning, replay, and configuration scenes without adding a new icon dependency.

## Implementation Design

- Keep the navigation definition in `MainLayout.vue` because the menu is small and only used by the layout.
- Represent menu items as an array with `path`, `label`, and `icon`.
- Bind Element Plus `el-aside` width to a computed `asideWidth`.
- Bind `el-menu` `collapse` to the reactive sidebar state.
- Store collapsed state under a stable `localStorage` key such as `sqlmon.sidebar.collapsed`.
- Use CSS transitions for sidebar width and menu label visibility through Element Plus collapse behavior.
- In collapsed mode, hide the brand text and keep the collapse button centered.

## Error Handling

- If `localStorage` is unavailable or contains an unexpected value, default to expanded mode.
- Persist failures are ignored because they should not block navigation.

## Testing

- Add focused frontend unit coverage around the sidebar collapsed-state helper functions if practical in the current toolchain.
- Run `npm run build` to verify Vue type checking and production bundling.
- Use browser verification to confirm:
  - icons render for every menu item,
  - the collapse toggle changes the sidebar width,
  - labels are hidden in collapsed mode,
  - the collapsed state survives reload,
  - the layout has no horizontal overflow.

## Out Of Scope

- Drawer navigation for mobile.
- User account preferences stored on the backend.
- Reworking the router or moving navigation into a standalone module.
