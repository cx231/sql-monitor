import { readFileSync } from 'node:fs';

const layout = readFileSync(new URL('../src/layouts/MainLayout.vue', import.meta.url), 'utf8');
const router = readFileSync(new URL('../src/router/index.ts', import.meta.url), 'utf8');
const usersView = readFileSync(new URL('../src/views/UsersView.vue', import.meta.url), 'utf8');
const types = readFileSync(new URL('../src/api/types.ts', import.meta.url), 'utf8');

const checks = [
  {
    name: 'sidebar includes user management with user icon',
    pass:
      layout.includes("path: '/settings/users'") &&
      layout.includes("label: '用户管理'") &&
      layout.includes('UserFilled'),
  },
  {
    name: 'router exposes user management page',
    pass:
      router.includes("path: 'settings/users'") &&
      router.includes("name: 'settings-users'") &&
      router.includes('UsersView'),
  },
  {
    name: 'user management page supports create edit disable and password reset',
    pass:
      usersView.includes('新增用户') &&
      usersView.includes('编辑') &&
      usersView.includes('重置密码') &&
      usersView.includes('禁用') &&
      usersView.includes('/disable') &&
      usersView.includes('/reset-password'),
  },
  {
    name: 'user management page does not expose delete action text',
    pass: !usersView.includes('删除'),
  },
  {
    name: 'role permissions follow product matrix',
    pass:
      usersView.includes("viewer', label: 'Viewer', description: '基础指标只读") &&
      usersView.includes("developer', label: 'Developer', description: 'Session、SQL、历史和完整 SQL") &&
      usersView.includes("dba', label: 'DBA', description: '全部监控、Kill 和审计") &&
      usersView.includes("admin', label: 'Admin', description: '实例、用户和系统配置"),
  },
  {
    name: 'frontend types include user role and status',
    pass:
      types.includes("export type UserRole = 'viewer' | 'developer' | 'dba' | 'admin'") &&
      types.includes("export type UserStatus = 'active' | 'disabled'"),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('User management checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('User management checks passed.');
