<template>
  <el-container class="main-layout">
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
      <div class="main-layout__user-footer">
        <el-tooltip
          v-if="isSidebarCollapsed"
          placement="right"
          :content="`${currentUsername} · ${formattedLoginTime}`"
        >
          <div class="main-layout__user-icon">
            <el-icon><User /></el-icon>
          </div>
        </el-tooltip>

        <div v-else class="main-layout__user-info">
          <div class="main-layout__user-name">
            <el-icon><User /></el-icon>
            <span>{{ currentUsername }}</span>
          </div>
          <div class="main-layout__login-time">
            <el-icon><Clock /></el-icon>
            <span>{{ formattedLoginTime }}</span>
          </div>
        </div>

        <el-tooltip :disabled="!isSidebarCollapsed" placement="right" content="退出登录">
          <el-button
            class="main-layout__logout-button"
            :class="{ 'is-collapsed': isSidebarCollapsed }"
            text
            :circle="isSidebarCollapsed"
            @click="logout"
          >
            <el-icon><SwitchButton /></el-icon>
            <span v-if="!isSidebarCollapsed">退出登录</span>
          </el-button>
        </el-tooltip>
      </div>
    </el-aside>

    <el-container>
      <el-header class="main-layout__header">
        <span>{{ pageTitle }}</span>
        <div class="main-layout__header-actions">
          <el-radio-group v-model="themeMode" size="small" aria-label="配色方案">
            <el-radio-button label="light">浅色</el-radio-button>
            <el-radio-button label="dark">深色</el-radio-button>
          </el-radio-group>
        </div>
      </el-header>
      <el-main class="main-layout__content">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import {
  Clock,
  Connection,
  DataAnalysis,
  DataLine,
  Document,
  Finished,
  Expand,
  Fold,
  Setting,
  SwitchButton,
  User,
  UserFilled,
  VideoPlay,
  Warning,
} from '@element-plus/icons-vue';
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';
import { useThemeStore, type ThemeMode } from '@/stores/theme';

const SIDEBAR_COLLAPSED_KEY = 'sqlmon.sidebar.collapsed';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const themeStore = useThemeStore();

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
    // Navigation remains usable when persistence is unavailable.
  }
}

const activePath = computed(() => route.path);
const pageTitle = computed(() => String(route.meta.title ?? '监控'));
const themeMode = computed({
  get: () => themeStore.mode,
  set: (mode: ThemeMode) => themeStore.setMode(mode),
});
const currentUsername = computed(() => {
  const user = authStore.user;
  return user?.displayName || user?.username || '当前用户';
});
const formattedLoginTime = computed(() => formatLoginTime(authStore.loginAt));
const isSidebarCollapsed = ref(readSidebarCollapsed());
const asideWidth = computed(() => (isSidebarCollapsed.value ? '64px' : '220px'));
const collapseIcon = computed(() => (isSidebarCollapsed.value ? Expand : Fold));
const navigationItems = [
  { path: '/dashboard', label: '仪表盘', icon: DataLine },
  { path: '/sessions', label: '会话监控', icon: Connection },
  { path: '/sqls', label: 'SQL 分析', icon: Document },
  { path: '/blocking', label: '阻塞分析', icon: Warning },
  { path: '/indexes/missing', label: '缺失索引', icon: Finished },
  { path: '/indexes/fragmentation', label: '索引碎片', icon: DataAnalysis },
  { path: '/replay', label: '回放分析', icon: VideoPlay },
  { path: '/settings/instances', label: '实例设置', icon: Setting },
  { path: '/settings/users', label: '用户管理', icon: UserFilled },
];

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
  writeSidebarCollapsed(isSidebarCollapsed.value);
}

function formatLoginTime(value: string | null): string {
  if (!value) {
    return '登录时间 -';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '登录时间 -';
  }

  return `登录 ${date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })}`;
}

async function logout() {
  authStore.logout();
  await router.replace('/login');
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
  min-height: 100vh;
  min-height: 0;
  background: var(--app-bg);
}

.main-layout__aside {
  min-height: 0;
  display: flex;
  flex-direction: column;
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

.main-layout__collapse-button:hover,
.main-layout__collapse-button:focus {
  color: var(--app-sidebar-active);
  background: color-mix(in srgb, var(--app-primary) 16%, transparent);
}

.main-layout__menu {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  border-right: 0;
}

:deep(.main-layout__menu.el-menu) {
  width: 100%;
  background-color: var(--app-sidebar-bg);
}

:deep(.main-layout__menu.el-menu--collapse) {
  width: 64px;
}

:deep(.main-layout__menu .el-menu-item) {
  color: var(--app-sidebar-text);
}

:deep(.main-layout__menu .el-icon) {
  color: inherit;
}

:deep(.main-layout__menu .el-menu-item.is-active) {
  color: var(--app-sidebar-active);
  background-color: color-mix(in srgb, var(--app-primary) 22%, transparent);
}

:deep(.main-layout__menu .el-menu-item:hover) {
  background-color: color-mix(in srgb, var(--app-primary) 14%, transparent);
}

.main-layout__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 24px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-divider);
  color: var(--app-text-primary);
  font-weight: 600;
}

.main-layout__header-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.main-layout__user-footer {
  flex: 0 0 auto;
  display: grid;
  gap: clamp(6px, 1.6vh, 10px);
  padding: clamp(8px, 1.8vh, 12px);
  border-top: 1px solid var(--app-sidebar-divider);
}

.main-layout__aside.is-collapsed .main-layout__user-footer {
  justify-items: center;
  padding: 12px 8px;
}

.main-layout__user-info {
  min-width: 0;
  display: grid;
  gap: 6px;
  color: var(--app-sidebar-text);
}

.main-layout__user-name,
.main-layout__login-time {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.main-layout__user-name {
  color: var(--app-sidebar-active);
  font-size: 14px;
  font-weight: 600;
}

.main-layout__login-time {
  color: var(--app-sidebar-text);
  font-size: 12px;
}

.main-layout__user-name span,
.main-layout__login-time span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main-layout__user-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  color: var(--app-sidebar-active);
  background: color-mix(in srgb, var(--app-primary) 18%, transparent);
  border: 1px solid var(--app-sidebar-divider);
  border-radius: 6px;
}

.main-layout__logout-button {
  --el-button-text-color: var(--app-sidebar-text);
  --el-button-hover-bg-color: color-mix(in srgb, var(--app-primary) 18%, transparent);
  --el-button-hover-border-color: transparent;
  --el-button-hover-text-color: var(--app-sidebar-active);
  --el-button-active-text-color: var(--app-sidebar-active);

  width: 100%;
  justify-content: flex-start;
  gap: 8px;
  color: var(--app-sidebar-text);
  background: color-mix(in srgb, var(--app-primary) 8%, transparent);
}

.main-layout__logout-button.is-collapsed {
  width: 36px;
}

.main-layout__logout-button:hover,
.main-layout__logout-button:focus {
  color: var(--app-sidebar-active);
  background: color-mix(in srgb, var(--app-primary) 18%, transparent);
}

.main-layout__logout-button.el-button.is-text:not(.is-disabled):hover,
.main-layout__logout-button.el-button.is-text:not(.is-disabled):focus,
.main-layout__logout-button.el-button.is-text:not(.is-disabled):active {
  color: var(--app-sidebar-active);
  background-color: color-mix(in srgb, var(--app-primary) 18%, transparent);
}

@media (max-width: 760px) {
  .main-layout__header {
    height: auto;
    min-height: 56px;
    align-items: flex-start;
    flex-direction: column;
    padding-block: 12px;
  }

  .main-layout__header-actions {
    width: 100%;
    justify-content: space-between;
  }
}

.main-layout__content {
  padding: 24px;
  background: var(--app-bg);
}

:global(.placeholder-view) {
  padding: 24px;
  background: var(--app-surface);
  border: 1px solid var(--app-divider);
  border-radius: 8px;
}

:global(.placeholder-view h1) {
  margin: 0 0 8px;
  font-size: 22px;
  color: var(--app-text-primary);
}

:global(.placeholder-view p) {
  margin: 0;
  color: var(--app-text-secondary);
}
</style>
