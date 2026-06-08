import { readFileSync } from 'node:fs';

const view = readFileSync(new URL('../src/views/DashboardView.vue', import.meta.url), 'utf8');
const types = readFileSync(new URL('../src/api/types.ts', import.meta.url), 'utf8');

const checks = [
  {
    name: 'Dashboard shows network send rate card',
    pass: view.includes("title: '网络传送速率'") &&
      view.includes('network_send_rate_bytes_per_sec'),
  },
  {
    name: 'Dashboard shows network receive rate card',
    pass: view.includes("title: '网络接收速率'") &&
      view.includes('network_receive_rate_bytes_per_sec'),
  },
  {
    name: 'Dashboard renders separate network charts',
    pass: view.includes("renderChart(\n    'networkSend'") &&
      view.includes("renderChart(\n    'networkReceive'"),
  },
  {
    name: 'Frontend API type exposes split network rates',
    pass: types.includes('network_send_rate_bytes_per_sec') &&
      types.includes('network_receive_rate_bytes_per_sec') &&
      !types.includes('network_rate_bytes_per_sec'),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('Dashboard network split checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('Dashboard network split checks passed.');
