# Sidebar Icons And Collapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add icons to the left navigation and support a persisted icon-only collapsed sidebar.

**Architecture:** Keep navigation inside `MainLayout.vue`, backed by a small local menu item array and helper functions for localStorage persistence. Element Plus handles menu routing and collapse rendering while scoped CSS adjusts the brand area and widths.

**Tech Stack:** Vue 3, TypeScript, Element Plus, `@element-plus/icons-vue`, Vite build verification.

---

### Task 1: Add Sidebar State Helpers

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: Add helper functions before production UI changes**

Add a localStorage key and two helpers in the `<script setup>` block:

```ts
const SIDEBAR_COLLAPSED_KEY = 'sqlmon.sidebar.collapsed';

function readSidebarCollapsed(): boolean {
  try {
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
  } catch {
    return false;
  }
}

function writeSidebarCollapsed(value: boolean) {
  try {
    window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(value));
  } catch {
    // Navigation must remain usable even if persistence is unavailable.
  }
}
```

- [ ] **Step 2: Run build to catch type errors**

Run: `cd frontend && npm run build`

Expected: build passes or fails only on missing imports that will be added in Task 2.

### Task 2: Add Icons And Collapse UI

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: Import icons**

Import Element Plus icons:

```ts
import {
  Connection,
  DataLine,
  Document,
  Expand,
  Fold,
  Setting,
  VideoPlay,
  Warning,
} from '@element-plus/icons-vue';
```

- [ ] **Step 2: Add reactive sidebar state and menu config**

Add:

```ts
const isSidebarCollapsed = ref(readSidebarCollapsed());
const asideWidth = computed(() => (isSidebarCollapsed.value ? '64px' : '220px'));
const collapseIcon = computed(() => (isSidebarCollapsed.value ? Expand : Fold));
const navigationItems = [
  { path: '/dashboard', label: '仪表盘', icon: DataLine },
  { path: '/sessions', label: '会话监控', icon: Connection },
  { path: '/sqls', label: 'SQL 分析', icon: Document },
  { path: '/blocking', label: '阻塞分析', icon: Warning },
  { path: '/replay', label: '回放分析', icon: VideoPlay },
  { path: '/settings/instances', label: '实例设置', icon: Setting },
];

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
  writeSidebarCollapsed(isSidebarCollapsed.value);
}
```

Ensure `ref` is imported from Vue.

- [ ] **Step 3: Update template**

Replace the fixed `el-aside` and text menu items with:

```vue
<el-aside :width="asideWidth" class="main-layout__aside" :class="{ 'is-collapsed': isSidebarCollapsed }">
  <div class="main-layout__brand">
    <span v-if="!isSidebarCollapsed" class="main-layout__brand-text">SQL 实时监控</span>
    <el-button
      class="main-layout__collapse-button"
      text
      circle
      :aria-label="isSidebarCollapsed ? '展开导航栏' : '收起导航栏'"
      @click="toggleSidebar"
    >
      <el-icon><component :is="collapseIcon" /></el-icon>
    </el-button>
  </div>
  <el-menu
    class="main-layout__menu"
    router
    :collapse="isSidebarCollapsed"
    :default-active="activePath"
    background-color="var(--app-sidebar-bg)"
    text-color="var(--app-sidebar-text)"
    active-text-color="var(--app-sidebar-active)"
  >
    <el-menu-item v-for="item in navigationItems" :key="item.path" :index="item.path">
      <el-icon><component :is="item.icon" /></el-icon>
      <template #title>{{ item.label }}</template>
    </el-menu-item>
  </el-menu>
</el-aside>
```

- [ ] **Step 4: Run build**

Run: `cd frontend && npm run build`

Expected: TypeScript and Vite build pass.

### Task 3: Polish Layout Styling

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: Add scoped CSS**

Update CSS to transition width, align the brand row, size the collapsed menu, and keep icon-only mode clean:

```css
.main-layout__aside {
  overflow: hidden;
  background: var(--app-sidebar-bg);
  transition: width 0.2s ease;
}

.main-layout__brand {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 12px 0 20px;
  color: var(--app-sidebar-active);
  font-size: 17px;
  font-weight: 600;
  border-bottom: 1px solid var(--app-sidebar-divider);
}

.main-layout__aside.is-collapsed .main-layout__brand {
  justify-content: center;
  padding: 0;
}

.main-layout__brand-text {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}

.main-layout__collapse-button {
  flex: 0 0 auto;
  color: var(--app-sidebar-text);
}
```

Ensure the menu width is stable:

```css
:deep(.main-layout__menu.el-menu) {
  width: 100%;
  background-color: var(--app-sidebar-bg);
}

:deep(.main-layout__menu.el-menu--collapse) {
  width: 64px;
}
```

- [ ] **Step 2: Run build**

Run: `cd frontend && npm run build`

Expected: build passes.

### Task 4: Browser Verification

**Files:**
- No code changes unless browser verification exposes layout issues.

- [ ] **Step 1: Start local frontend**

Run: `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`

- [ ] **Step 2: Verify UI**

Open `http://127.0.0.1:5173` and verify:

- expanded sidebar shows six icons and six labels,
- collapse button reduces sidebar to about 64px,
- collapsed sidebar shows icons only,
- clicking the toggle again restores labels,
- collapsed state persists after browser reload,
- no horizontal overflow at desktop and mobile widths.

- [ ] **Step 3: Stop dev server**

Stop the Vite process after verification.

### Task 5: Final Verification

**Files:**
- No code changes.

- [ ] **Step 1: Run whitespace check**

Run: `git diff --check`

Expected: no output.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

Expected: build passes; existing Vite warnings are acceptable if unchanged.

- [ ] **Step 3: Review git status**

Run: `git status --short`

Expected: intended layout, docs, and previously pending requested changes are visible; no generated `dist` files should be staged or committed.
