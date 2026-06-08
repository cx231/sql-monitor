import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/views/BlockingView.vue', import.meta.url), 'utf8');

const checks = [
  {
    name: 'blocking page imports and renders kill confirmation dialog',
    pass:
      source.includes("import KillConfirmDialog from '@/components/KillConfirmDialog.vue'") &&
      source.includes('<KillConfirmDialog'),
  },
  {
    name: 'root blocker header exposes a Kill danger button',
    pass:
      source.includes('openRootKill(chain.root_session_id)') &&
      source.includes('type="danger"') &&
      />\s*Kill\s*<\/el-button>/.test(source),
  },
  {
    name: 'blocking kill action posts to existing kill endpoint',
    pass:
      source.includes("apiClient.post<KillResponse>('/kill'") &&
      source.includes('session_id: killSessionId.value') &&
      source.includes('await fetchBlocking()'),
  },
  {
    name: 'button text is Kill, not KILL PID',
    pass: !source.includes('KILL PID'),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('Blocking kill action checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('Blocking kill action checks passed.');
