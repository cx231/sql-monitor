import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/views/SqlsView.vue', import.meta.url), 'utf8');

const checks = [
  {
    name: 'SQL list has an operation column',
    pass: source.includes('title="操作"') && source.includes('openSqlDetail(row)'),
  },
  {
    name: 'SQL detail dialog renders full SQL text',
    pass: source.includes('sqlDetailVisible') && source.includes('<pre>{{ sqlDetail.sql_text || sqlDetail.sql_preview ||'),
  },
  {
    name: 'full SQL text is not clipped',
    pass: source.includes('white-space: pre-wrap') && source.includes('overflow-wrap: anywhere'),
  },
  {
    name: 'detail fetches row data from sql detail endpoint when needed',
    pass: source.includes("apiClient.get<SqlListItem>(`/sqls/${encodeURIComponent(row.sql_hash)}`"),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('SQL detail action checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('SQL detail action checks passed.');
