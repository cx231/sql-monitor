import { readFileSync } from 'node:fs';

const realtimeViews = [
  '../src/views/DashboardView.vue',
  '../src/views/SessionsView.vue',
  '../src/views/SqlsView.vue',
  '../src/views/BlockingView.vue',
];

const files = Object.fromEntries(
  realtimeViews.map((path) => [path, readFileSync(new URL(path, import.meta.url), 'utf8')]),
);
const types = readFileSync(new URL('../src/api/types.ts', import.meta.url), 'utf8');

const checks = [
  {
    name: 'real-time views use backend collect delay for stale state',
    pass: Object.values(files).every(
      (source) =>
        source.includes('collect_delay_seconds') &&
        source.includes('isRealtimeStale') &&
        source.includes('realtimeStaleText') &&
        source.includes(':stale-text="staleText"'),
    ),
  },
  {
    name: 'real-time views do not calculate stale state from browser clock',
    pass: Object.values(files).every((source) => !source.includes('staleSeconds')),
  },
  {
    name: 'frontend real-time response types expose collect delay',
    pass:
      /interface PageOut<T>[\s\S]*collect_delay_seconds: number;/.test(types) &&
      /interface BlockingOut[\s\S]*collect_delay_seconds: number;/.test(types) &&
      /interface DashboardOut[\s\S]*collect_delay_seconds: number;/.test(types),
  },
  {
    name: 'frontend instance type exposes collect status diagnosis fields',
    pass:
      types.includes('collect_status') ||
      readFileSync(new URL('../src/stores/instances.ts', import.meta.url), 'utf8').includes('last_success_at: string | null;'),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('Realtime stale delay checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('Realtime stale delay checks passed.');
