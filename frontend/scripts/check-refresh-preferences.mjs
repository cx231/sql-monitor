import { readFileSync } from 'node:fs';

const store = readFileSync(new URL('../src/stores/refresh.ts', import.meta.url), 'utf8');

const checks = [
  {
    name: '刷新间隔从 localStorage 初始化',
    pass:
      store.includes('REFRESH_INTERVAL_STORAGE_KEY') &&
      store.includes('readStoredIntervalSeconds()') &&
      store.includes('intervalSeconds: readStoredIntervalSeconds()'),
  },
  {
    name: '刷新间隔变更后写入 localStorage',
    pass:
      store.includes('writeStoredIntervalSeconds(this.intervalSeconds)') &&
      store.includes('localStorage.setItem(REFRESH_INTERVAL_STORAGE_KEY'),
  },
  {
    name: '刷新间隔只允许现有选项',
    pass:
      store.includes('REFRESH_INTERVAL_OPTIONS') &&
      store.includes('REFRESH_INTERVAL_OPTIONS.includes'),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('Refresh preference checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('Refresh preference checks passed.');
