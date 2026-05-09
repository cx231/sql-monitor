<template>
  <el-container class="main-layout">
    <el-aside width="220px" class="main-layout__aside">
      <div class="main-layout__brand">SQL 实时监控</div>
      <el-menu
        class="main-layout__menu"
        router
        :default-active="activePath"
        background-color="#17212f"
        text-color="#d8dee9"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/dashboard">仪表盘</el-menu-item>
        <el-menu-item index="/sessions">会话监控</el-menu-item>
        <el-menu-item index="/sqls">SQL 分析</el-menu-item>
        <el-menu-item index="/blocking">阻塞分析</el-menu-item>
        <el-menu-item index="/replay">回放分析</el-menu-item>
        <el-menu-item index="/settings/instances">实例设置</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="main-layout__header">
        <span>{{ pageTitle }}</span>
        <el-button text @click="logout">退出登录</el-button>
      </el-header>
      <el-main class="main-layout__content">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const activePath = computed(() => route.path);
const pageTitle = computed(() => String(route.meta.title ?? '监控'));

async function logout() {
  authStore.logout();
  await router.replace('/login');
}
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
  background: #f4f6f8;
}

.main-layout__aside {
  background: #17212f;
}

.main-layout__brand {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  color: #ffffff;
  font-size: 17px;
  font-weight: 600;
  border-bottom: 1px solid rgb(255 255 255 / 10%);
}

.main-layout__menu {
  border-right: 0;
}

.main-layout__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  color: #1f2937;
  font-weight: 600;
}

.main-layout__content {
  padding: 24px;
}

:global(.placeholder-view) {
  padding: 24px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

:global(.placeholder-view h1) {
  margin: 0 0 8px;
  font-size: 22px;
  color: #111827;
}

:global(.placeholder-view p) {
  margin: 0;
  color: #6b7280;
}
</style>
