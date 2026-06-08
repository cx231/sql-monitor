import { readFileSync } from 'node:fs';

const view = readFileSync(new URL('../src/views/IndexFragmentationView.vue', import.meta.url), 'utf8');
const router = readFileSync(new URL('../src/router/index.ts', import.meta.url), 'utf8');
const layout = readFileSync(new URL('../src/layouts/MainLayout.vue', import.meta.url), 'utf8');
const types = readFileSync(new URL('../src/api/types.ts', import.meta.url), 'utf8');

const checks = [
  {
    name: '独立索引碎片路由存在',
    pass: router.includes("path: 'indexes/fragmentation'") && router.includes("title: '索引碎片'"),
  },
  {
    name: '侧边栏包含索引碎片入口',
    pass: layout.includes("path: '/indexes/fragmentation'") && layout.includes("label: '索引碎片'"),
  },
  {
    name: '页面加载用户库和碎片检查 API',
    pass: view.includes("apiClient.get<IndexDatabaseListOut>('/indexes/databases'") &&
      view.includes("apiClient.get<IndexFragmentationListOut>('/indexes/fragmentation'"),
  },
  {
    name: '页面执行碎片维护 API',
    pass: view.includes("'/indexes/fragmentation/actions'") &&
      view.includes('执行 {{ row.recommended_action }}'),
  },
  {
    name: '页面展示 Online rebuild 状态和确认文案',
    pass: view.includes('支持 Online Rebuild') &&
      view.includes('REBUILD WITH (ONLINE = ON)') &&
      view.includes('使用 ONLINE = ON'),
  },
  {
    name: '页面支持分页加载索引碎片',
    pass: view.includes('v-model:current-page="page"') &&
      view.includes('v-model:page-size="pageSize"') &&
      view.includes('const pageSize = ref(20)') &&
      view.includes(':page-sizes="[20, 50, 100, 200, 500]"') &&
      view.includes('@current-change="handlePageChange"') &&
      view.includes('page_size: pageSize.value') &&
      view.includes(':total="total"'),
  },
  {
    name: '分页只使用后端返回当前页并避免连点锁死',
    pass: view.includes('rows.value = data.items.slice(0, pageSize.value)') &&
      view.includes(':disabled="fragmentationLoading"') &&
      view.includes(':pager-count="5"') &&
      view.includes('let fragmentationAbortController: AbortController | null = null') &&
      view.includes('signal: fragmentationAbortController.signal'),
  },
  {
    name: '翻页时保留表格并丢弃过期响应',
    pass: view.includes('v-loading="fragmentationLoading"') &&
      view.includes('let fragmentationRequestSeq = 0') &&
      view.includes('if (requestSeq !== fragmentationRequestSeq)') &&
      view.includes(':disabled="!selectedDatabase || fragmentationLoading"'),
  },
  {
    name: '页面固定格式显示快照最后更新时间',
    pass: view.includes('class="snapshot-panel"') &&
      view.includes('快照最后更新时间：{{ snapshotUpdatedAtText }}') &&
      view.includes("import { formatSnapshotDateTime") &&
      view.includes('const snapshotUpdatedAtText = computed(() => formatSnapshotDateTime(checkedAt.value))'),
  },
  {
    name: '页面展示本地快照采集状态',
    pass: view.includes('collectionStatus') &&
      view.includes('collection_error') &&
      view.includes('stale') &&
      view.includes('等待 collector 采集索引碎片数据') &&
      view.includes('刷新'),
  },
  {
    name: '前端类型包含碎片检查结构',
    pass: types.includes('export interface IndexFragmentationItem') &&
      types.includes('export interface IndexFragmentationListOut') &&
      types.includes('export interface IndexFragmentationActionResponse') &&
      types.includes('collection_status: string;') &&
      types.includes('stale: boolean;') &&
      types.includes('page_size: number;') &&
      types.includes('total: number;'),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('Index fragmentation module checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('Index fragmentation module checks passed.');
