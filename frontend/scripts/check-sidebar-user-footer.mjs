import { readFileSync } from 'node:fs';

const layout = readFileSync(new URL('../src/layouts/MainLayout.vue', import.meta.url), 'utf8');
const authStore = readFileSync(new URL('../src/stores/auth.ts', import.meta.url), 'utf8');

const checks = [
  {
    name: 'logout button lives in the sidebar footer',
    pass: layout.includes('main-layout__user-footer') && layout.includes('main-layout__logout-button'),
  },
  {
    name: 'header no longer contains logout action',
    pass: !layout.includes('<el-button text @click="logout">退出登录</el-button>'),
  },
  {
    name: 'logout button has an icon',
    pass: layout.includes('<SwitchButton />'),
  },
  {
    name: 'logout button keeps readable colors on hover',
    pass:
      layout.includes('.main-layout__logout-button.el-button.is-text:not(.is-disabled):hover') &&
      layout.includes('background-color: color-mix(in srgb, var(--app-primary) 18%, transparent)') &&
      layout.includes('color: var(--app-sidebar-active)'),
  },
  {
    name: 'sidebar keeps footer visible while page height changes',
    pass:
      layout.includes('height: 100vh') &&
      layout.includes('.main-layout__menu') &&
      layout.includes('min-height: 0') &&
      layout.includes('overflow-y: auto'),
  },
  {
    name: 'sidebar shows login username and login time',
    pass: layout.includes('currentUsername') && layout.includes('formattedLoginTime'),
  },
  {
    name: 'auth store persists user and login time',
    pass: authStore.includes('AUTH_STATE_STORAGE_KEY') && authStore.includes('loginAt'),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('Sidebar user footer checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('Sidebar user footer checks passed.');
