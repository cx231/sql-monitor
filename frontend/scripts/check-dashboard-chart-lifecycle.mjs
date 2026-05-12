import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/views/DashboardView.vue', import.meta.url), 'utf8');

const checks = [
  {
    name: 'dashboard content stays mounted during refresh',
    pass: source.includes(':loading="loading && !dashboard"'),
  },
  {
    name: 'stale ECharts instance is recreated for a new DOM element',
    pass: source.includes('chart.getDom() !== element'),
  },
  {
    name: 'chart instances are disposed when their DOM refs are removed',
    pass: source.includes('disposeChart('),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('Dashboard chart lifecycle checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('Dashboard chart lifecycle checks passed.');
