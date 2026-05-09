import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';

import { getAccessToken } from '@/api/client';
import MainLayout from '@/layouts/MainLayout.vue';
import BlockingView from '@/views/BlockingView.vue';
import DashboardView from '@/views/DashboardView.vue';
import InstancesView from '@/views/InstancesView.vue';
import LoginView from '@/views/LoginView.vue';
import ReplayView from '@/views/ReplayView.vue';
import SessionsView from '@/views/SessionsView.vue';
import SqlsView from '@/views/SqlsView.vue';

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { title: '登录' },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: DashboardView,
        meta: { title: '仪表盘' },
      },
      {
        path: 'sessions',
        name: 'sessions',
        component: SessionsView,
        meta: { title: '会话监控' },
      },
      {
        path: 'sqls',
        name: 'sqls',
        component: SqlsView,
        meta: { title: 'SQL 分析' },
      },
      {
        path: 'blocking',
        name: 'blocking',
        component: BlockingView,
        meta: { title: '阻塞分析' },
      },
      {
        path: 'replay',
        name: 'replay',
        component: ReplayView,
        meta: { title: '回放分析' },
      },
      {
        path: 'settings/instances',
        name: 'settings-instances',
        component: InstancesView,
        meta: { title: '实例设置' },
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const loggedIn = Boolean(getAccessToken());

  if (to.name !== 'login' && !loggedIn) {
    return { name: 'login' };
  }

  if (to.name === 'login' && loggedIn) {
    return { name: 'dashboard' };
  }

  return true;
});

router.afterEach((to) => {
  document.title = `${String(to.meta.title ?? '监控')} - SQL Server 实时监控`;
});

export default router;
