<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <AutoRefreshControl />
    </div>

    <DataState :loading="loading" :error="error" :empty="!rows.length" :stale="isStale" :stale-text="staleText">
      <div class="table-panel">
        <div class="snapshot-line">
          快照时间：{{ formatDateTime(snapshotTime) }}，采集延迟：{{ collectDelaySeconds }} 秒
        </div>
        <vxe-table
          :data="rows"
          size="small"
          border
          height="620"
          :sort-config="{ remote: true, defaultSort: { field: sortBy, order: sortOrder } }"
          @sort-change="handleSortChange"
        >
          <vxe-column field="session_id" title="会话" width="80" />
          <vxe-column field="database_name" title="数据库" width="120" />
          <vxe-column field="status" title="状态" width="100" :formatter="statusFormatter" />
          <vxe-column field="command" title="命令" width="110" />
          <vxe-column field="duration_ms" title="耗时" width="110" align="right" sortable :formatter="durationFormatter" />
          <vxe-column field="cpu_time_ms" title="CPU" width="110" align="right" sortable :formatter="numberFormatter" />
          <vxe-column field="logical_reads" title="逻辑读" width="120" align="right" sortable :formatter="numberFormatter" />
          <vxe-column field="reads" title="读" width="100" align="right" sortable :formatter="numberFormatter" />
          <vxe-column field="writes" title="写" width="100" align="right" sortable :formatter="numberFormatter" />
          <vxe-column field="wait_type" title="等待类型" width="140" show-overflow />
          <vxe-column field="wait_time_ms" title="等待" width="110" align="right" sortable :formatter="durationFormatter" />
          <vxe-column field="blocking_session_id" title="阻塞源" width="90" />
          <vxe-column field="sql_preview" title="SQL 预览" min-width="360" show-overflow />
          <vxe-column title="操作" width="88" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openSqlDetail(row)">详情</el-button>
            </template>
          </vxe-column>
        </vxe-table>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          class="pager"
          layout="total, sizes, prev, pager, next"
          :page-sizes="[20, 50, 100, 200]"
          :total="total"
        />
      </div>
    </DataState>

    <el-dialog v-model="sqlDetailVisible" title="SQL 详情" width="860px" destroy-on-close>
      <DataState
        :loading="sqlDetailLoading"
        :error="sqlDetailError"
        :empty="!sqlDetail"
        loading-text="正在加载 SQL 详情..."
        empty-text="暂无 SQL 详情"
      >
        <template v-if="sqlDetail">
          <div class="sql-detail">
            <div class="sql-detail__grid">
              <div v-for="item in sqlDetailFields" :key="item.label" class="sql-detail__item">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
            <section class="sql-detail__section">
              <h3>完整 SQL</h3>
              <pre>{{ sqlDetail.sql_text || sqlDetail.sql_preview || '-' }}</pre>
            </section>
          </div>
        </template>
      </DataState>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';

import { apiClient } from '@/api/client';
import type { PageOut, SqlListItem } from '@/api/types';
import AutoRefreshControl from '@/components/AutoRefreshControl.vue';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import { useInstancesStore } from '@/stores/instances';
import { useRefreshStore } from '@/stores/refresh';
import { formatDateTime, formatDurationMs, formatNumber, formatSessionStatus } from '@/utils/format';
import { isRealtimeStale, realtimeStaleText } from '@/utils/realtimeFreshness';

const instancesStore = useInstancesStore();
const refreshStore = useRefreshStore();
const rows = ref<SqlListItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const sortBy = ref('cpu_time_ms');
const sortOrder = ref<'asc' | 'desc'>('desc');
const snapshotTime = ref<string | null>(null);
const collectDelaySeconds = ref(0);
const loading = ref(false);
const error = ref('');
const sqlDetailVisible = ref(false);
const sqlDetailLoading = ref(false);
const sqlDetailError = ref('');
const sqlDetail = ref<SqlListItem | null>(null);

const isStale = computed(() => {
  return isRealtimeStale(collectDelaySeconds.value);
});
const staleText = computed(() => realtimeStaleText(instancesStore.currentInstance));

const sqlDetailFields = computed(() => {
  const row = sqlDetail.value;
  if (!row) {
    return [];
  }

  return [
    { label: '会话', value: formatNumber(row.session_id) },
    { label: '请求', value: formatNumber(row.request_id) },
    { label: '数据库', value: row.database_name || '-' },
    { label: '状态', value: formatSessionStatus(row.status) },
    { label: '命令', value: row.command || '-' },
    { label: '耗时', value: formatDurationMs(row.duration_ms) },
    { label: 'CPU', value: formatNumber(row.cpu_time_ms) },
    { label: '逻辑读', value: formatNumber(row.logical_reads) },
    { label: '物理读', value: formatNumber(row.reads) },
    { label: '写入', value: formatNumber(row.writes) },
    { label: '等待类型', value: row.wait_type || '-' },
    { label: '等待时间', value: formatDurationMs(row.wait_time_ms) },
    { label: '阻塞源', value: formatNumber(row.blocking_session_id) },
    { label: 'SQL Hash', value: row.sql_hash || '-' },
  ];
});

async function fetchSqls() {
  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId) {
    return;
  }

  loading.value = true;
  error.value = '';
  try {
    await instancesStore.fetchInstances();
    const { data } = await apiClient.get<PageOut<SqlListItem>>('/sqls', {
      params: {
        instance_id: instanceId,
        page: page.value,
        page_size: pageSize.value,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
      },
    });
    rows.value = data.items;
    total.value = data.total;
    snapshotTime.value = data.snapshot_time;
    collectDelaySeconds.value = data.collect_delay_seconds;
  } catch {
    error.value = '无法加载 SQL 数据';
  } finally {
    loading.value = false;
  }
}

function resetAndFetchSqls() {
  if (page.value === 1) {
    void fetchSqls();
    return;
  }

  page.value = 1;
}

function handleSortChange({ field, order }: { field: string; order: string | null }) {
  sortBy.value = field || 'cpu_time_ms';
  sortOrder.value = order === 'asc' ? 'asc' : 'desc';
  resetAndFetchSqls();
}

async function openSqlDetail(row: SqlListItem) {
  sqlDetailVisible.value = true;
  sqlDetailError.value = '';
  sqlDetail.value = row;

  if (!row.sql_hash || row.sql_text) {
    return;
  }

  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId) {
    return;
  }

  sqlDetailLoading.value = true;
  try {
    const { data } = await apiClient.get<SqlListItem>(`/sqls/${encodeURIComponent(row.sql_hash)}`, {
      params: { instance_id: instanceId },
    });
    sqlDetail.value = data;
  } catch {
    sqlDetailError.value = '无法加载 SQL 完整详情';
    ElMessage.error(sqlDetailError.value);
  } finally {
    sqlDetailLoading.value = false;
  }
}

const numberFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatNumber(cellValue);
const durationFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatDurationMs(cellValue);
const statusFormatter = ({ cellValue }: { cellValue: string | null | undefined }) => formatSessionStatus(cellValue);

onMounted(async () => {
  await instancesStore.fetchInstances();
  await fetchSqls();
});

watch(() => instancesStore.currentInstance?.id, () => {
  resetAndFetchSqls();
});
watch([page, pageSize], fetchSqls);
watch(() => refreshStore.tick, fetchSqls);
</script>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}

.page__toolbar,
.table-panel {
  padding: 12px;
  background: var(--app-surface);
  border: 1px solid var(--app-divider);
  border-radius: 6px;
}

.page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.snapshot-line {
  margin-bottom: 10px;
  color: var(--app-text-secondary);
  font-size: 13px;
}

.pager {
  margin-top: 12px;
  justify-content: flex-end;
}

.sql-detail {
  display: grid;
  gap: 14px;
}

.sql-detail__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.sql-detail__item {
  min-width: 0;
  padding: 10px;
  background: var(--app-surface-muted);
  border: 1px solid var(--app-divider);
  border-radius: 6px;
}

.sql-detail__item span {
  display: block;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.sql-detail__item strong {
  display: block;
  margin-top: 6px;
  overflow-wrap: anywhere;
  color: var(--app-text-primary);
  font-size: 13px;
  font-weight: 600;
}

.sql-detail__section h3 {
  margin: 0 0 8px;
  color: var(--app-text-primary);
  font-size: 14px;
}

.sql-detail__section pre {
  max-height: 420px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--app-text-primary);
  background: var(--app-surface-muted);
  border: 1px solid var(--app-divider);
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 760px) {
  .sql-detail__grid {
    grid-template-columns: 1fr;
  }
}
</style>
