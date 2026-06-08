import { readFileSync } from 'node:fs';

const view = readFileSync(new URL('../src/views/MissingIndexesView.vue', import.meta.url), 'utf8');
const router = readFileSync(new URL('../src/router/index.ts', import.meta.url), 'utf8');
const layout = readFileSync(new URL('../src/layouts/MainLayout.vue', import.meta.url), 'utf8');
const types = readFileSync(new URL('../src/api/types.ts', import.meta.url), 'utf8');

const checks = [
  {
    name: '独立缺失索引路由存在',
    pass: router.includes("path: 'indexes/missing'") && router.includes("title: '缺失索引'"),
  },
  {
    name: '侧边栏包含缺失索引入口',
    pass: layout.includes("path: '/indexes/missing'") && layout.includes("label: '缺失索引'"),
  },
  {
    name: '页面加载用户库和缺失索引 API',
    pass: view.includes("apiClient.get<IndexDatabaseListOut>('/indexes/databases'") &&
      view.includes("apiClient.get<MissingIndexListOut>('/indexes/missing'"),
  },
  {
    name: '页面创建索引并处理索引名冲突',
    pass: view.includes("apiClient.post<IndexCreateResponse>('/indexes'") &&
      view.includes('INDEX_NAME_CONFLICT') &&
      view.includes('索引名已存在，请修改索引名'),
  },
  {
    name: '页面确认弹窗允许编辑索引名',
    pass: view.includes('v-model="indexName"') && view.includes('title="新建索引"'),
  },
  {
    name: '页面支持分页加载缺失索引',
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
      view.includes(':disabled="missingLoading"') &&
      view.includes(':pager-count="5"') &&
      view.includes('let missingAbortController: AbortController | null = null') &&
      view.includes('signal: missingAbortController.signal'),
  },
  {
    name: '翻页时保留表格并丢弃过期响应',
    pass: view.includes('v-loading="missingLoading"') &&
      view.includes('let missingRequestSeq = 0') &&
      view.includes('if (requestSeq !== missingRequestSeq)') &&
      view.includes(':disabled="!selectedDatabase || missingLoading"'),
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
      view.includes('等待 collector 采集缺失索引数据') &&
      view.includes('刷新'),
  },
  {
    name: '前端类型包含缺失索引结构',
    pass: types.includes('export interface MissingIndexItem') &&
      types.includes('export interface IndexCreatePayload') &&
      types.includes('export interface IndexCreateResponse') &&
      types.includes('collection_status: string;') &&
      types.includes('stale: boolean;') &&
      types.includes('page_size: number;') &&
      types.includes('total: number;'),
  },
];

const failures = checks.filter((check) => !check.pass);

if (failures.length > 0) {
  console.error('Missing index module checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure.name}`);
  }
  process.exit(1);
}

console.log('Missing index module checks passed.');
