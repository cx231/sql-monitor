<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <AutoRefreshControl />
    </div>

    <DataState :loading="loading" :error="error" :empty="!rows.length" :stale="isStale">
      <div class="table-panel">
        <div class="snapshot-line">快照时间：{{ formatDateTime(snapshotTime) }}</div>
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
          <vxe-column field="status" title="状态" width="100" />
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
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import { apiClient } from '@/api/client';
import type { PageOut, SqlListItem } from '@/api/types';
import AutoRefreshControl from '@/components/AutoRefreshControl.vue';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import { useInstancesStore } from '@/stores/instances';
import { useRefreshStore } from '@/stores/refresh';
import { formatDateTime, formatDurationMs, formatNumber, staleSeconds } from '@/utils/format';

const instancesStore = useInstancesStore();
const refreshStore = useRefreshStore();
const rows = ref<SqlListItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const sortBy = ref('cpu_time_ms');
const sortOrder = ref<'asc' | 'desc'>('desc');
const snapshotTime = ref<string | null>(null);
const loading = ref(false);
const error = ref('');

const isStale = computed(() => {
  const seconds = staleSeconds(snapshotTime.value);
  return seconds !== null && seconds > 60;
});

async function fetchSqls() {
  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId) {
    return;
  }

  loading.value = true;
  error.value = '';
  try {
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
  } catch {
    error.value = '无法加载 SQL 数据';
  } finally {
    loading.value = false;
  }
}

function handleSortChange({ field, order }: { field: string; order: string | null }) {
  sortBy.value = field || 'cpu_time_ms';
  sortOrder.value = order === 'asc' ? 'asc' : 'desc';
  page.value = 1;
  void fetchSqls();
}

const numberFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatNumber(cellValue);
const durationFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatDurationMs(cellValue);

onMounted(async () => {
  await instancesStore.fetchInstances();
  await fetchSqls();
});

watch(() => instancesStore.currentInstance?.id, () => {
  page.value = 1;
  void fetchSqls();
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
  background: #ffffff;
  border: 1px solid #e5e7eb;
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
  color: #606266;
  font-size: 13px;
}

.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
