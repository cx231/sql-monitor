import { readFileSync } from 'node:fs';

const view = readFileSync(new URL('../src/views/InstancesView.vue', import.meta.url), 'utf8');
const store = readFileSync(new URL('../src/stores/instances.ts', import.meta.url), 'utf8');

const checks = [
  {
    name: '实例表单包含两个索引采集间隔字段',
    pass:
      view.includes('缺失索引采集间隔（分钟）') &&
      view.includes('索引碎片采集间隔（分钟）') &&
      view.includes('missing_index_collect_interval_seconds') &&
      view.includes('index_fragmentation_collect_interval_seconds'),
  },
  {
    name: '实例表单默认索引采集间隔为10分钟',
    pass:
      view.includes('missing_index_collect_interval_seconds: 600') &&
      view.includes('index_fragmentation_collect_interval_seconds: 600'),
  },
  {
    name: '实例 store 提交和回显索引采集间隔',
    pass:
      store.includes('missing_index_collect_interval_seconds: number;') &&
      store.includes('index_fragmentation_collect_interval_seconds: number;') &&
      store.includes('missing_index_collect_interval_seconds: form.missing_index_collect_interval_seconds') &&
      store.includes('index_fragmentation_collect_interval_seconds: form.index_fragmentation_collect_interval_seconds'),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('Instance index interval checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('Instance index interval checks passed.');
