# Theme Mode Design

## Goal

Add an IT Management Professional theme system with light and dark modes. Users can switch modes from the main layout, and the choice persists locally.

## Scope

This change covers the frontend only:

1. Add a global theme token layer based on the provided palette.
2. Add a light/dark theme selector in the main layout header.
3. Persist the selected theme in `localStorage`.
4. Apply theme tokens to app layout, login page, common panels, dialogs, tables, and key status colors.
5. Keep existing routes, API behavior, authentication, and instance management logic unchanged.

## Theme Tokens

The app uses these semantic CSS variables:

```text
--app-bg
--app-surface
--app-surface-muted
--app-divider
--app-text-primary
--app-text-secondary
--app-text-disabled
--app-primary
--app-primary-hover
--app-success
--app-warning
--app-error
--app-info
--app-on-primary
```

Light and dark modes map directly to the user-provided palette.

## Element Plus and vxe-table

The global theme file also maps app tokens to Element Plus variables such as:

```text
--el-color-primary
--el-bg-color
--el-bg-color-overlay
--el-text-color-primary
--el-border-color
```

vxe-table receives minimal global overrides for table background, text, header background, and borders.

## UX

The main header adds a compact segmented control with two options:

1. 浅色
2. 深色

The selector is placed near the logout action. Login uses the saved theme even before the user authenticates.

## Persistence

The theme store writes `sqlmon.theme_mode` to `localStorage`. On startup it reads the stored value, defaults to `light`, and updates `document.documentElement.dataset.theme`.

## Testing

Frontend verification:

1. Production build succeeds.
2. Browser inspection confirms light and dark modes both render without obvious contrast regressions or horizontal overflow.
3. Theme choice survives a reload.
