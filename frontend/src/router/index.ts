import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';

import MainLayout from '@/layouts/MainLayout.vue';

const placeholderView = (title: string) => ({
  template: `
    <section class="placeholder-view">
      <h1>${title}</h1>
      <p>该页面将在后续任务中实现。</p>
    </section>
  `,
});

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: placeholderView('登录'),
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
        component: placeholderView('仪表盘'),
        meta: { title: '仪表盘' },
      },
      {
        path: 'sessions',
        name: 'sessions',
        component: placeholderView('会话监控'),
        meta: { title: '会话监控' },
      },
      {
        path: 'sqls',
        name: 'sqls',
        component: placeholderView('SQL 分析'),
        meta: { title: 'SQL 分析' },
      },
      {
        path: 'blocking',
        name: 'blocking',
        component: placeholderView('阻塞分析'),
        meta: { title: '阻塞分析' },
      },
      {
        path: 'replay',
        name: 'replay',
        component: placeholderView('回放分析'),
        meta: { title: '回放分析' },
      },
      {
        path: 'settings/instances',
        name: 'settings-instances',
        component: placeholderView('实例设置'),
        meta: { title: '实例设置' },
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.afterEach((to) => {
  document.title = `${String(to.meta.title ?? '监控')} - SQL Server 实时监控`;
});

export default router;
