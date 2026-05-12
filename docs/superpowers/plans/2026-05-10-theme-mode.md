# Theme Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent light/dark theme selection using the provided IT Management Professional palette.

**Architecture:** Create a global CSS token file, a small Pinia theme store, and a header selector. Replace hard-coded app shell and common panel colors with CSS variables, while Element Plus and vxe-table inherit the palette from global variable overrides.

**Tech Stack:** Vue 3, Pinia, Element Plus, vxe-table, CSS custom properties.

---

### Task 1: Theme Tokens and Store

**Files:**
- Create: `frontend/src/styles/theme.css`
- Create: `frontend/src/stores/theme.ts`
- Modify: `frontend/src/main.ts`

- [ ] **Step 1: Create theme token CSS**

Define `:root[data-theme='light']` and `:root[data-theme='dark']` variables from the supplied palette. Add Element Plus and vxe-table variable overrides.

- [ ] **Step 2: Create theme store**

Create a Pinia store with `mode`, `setMode`, and `toggleMode`. Read/write `sqlmon.theme_mode`; apply mode to `document.documentElement.dataset.theme`.

- [ ] **Step 3: Import CSS and initialize theme**

Import `frontend/src/styles/theme.css` in `frontend/src/main.ts`; call the theme store after `app.use(createPinia())` and before mount.

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: PASS.

### Task 2: Theme Selector and App Shell

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Add selector**

Add a compact Element Plus radio group in the header with `浅色` and `深色`, bound to the theme store.

- [ ] **Step 2: Apply shell tokens**

Replace app shell, aside, header, content, and login panel hard-coded colors with `var(--app-*)` tokens.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: PASS.

### Task 3: Common Components and Pages

**Files:**
- Modify: `frontend/src/components/DataState.vue`
- Modify: `frontend/src/components/InstanceSelector.vue`
- Modify: `frontend/src/components/SessionDetailDrawer.vue`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/views/SessionsView.vue`
- Modify: `frontend/src/views/SqlsView.vue`
- Modify: `frontend/src/views/BlockingView.vue`
- Modify: `frontend/src/views/ReplayView.vue`
- Modify: `frontend/src/views/InstancesView.vue`

- [ ] **Step 1: Replace repeated panel colors**

Change white panel backgrounds, gray borders, and gray text to theme variables.

- [ ] **Step 2: Replace dialog-specific colors**

Update the instance dialog section markers, side panel, result states, and footer text to use theme variables and semantic colors.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: PASS.

### Task 4: Browser Verification

**Files:**
- No source edits expected.

- [ ] **Step 1: Inspect light mode**

Open the local app, set `localStorage.sqlmon.theme_mode = 'light'`, reload, and confirm the main shell and login page render in light mode.

- [ ] **Step 2: Inspect dark mode**

Set `localStorage.sqlmon.theme_mode = 'dark'`, reload, and confirm the main shell, login page, tables, dialogs, and controls render in dark mode without horizontal overflow.

- [ ] **Step 3: Final build**

Run: `cd frontend && npm run build`
Expected: PASS.
