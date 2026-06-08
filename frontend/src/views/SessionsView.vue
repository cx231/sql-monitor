<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <AutoRefreshControl />
    </div>

    <div class="filters">
      <el-select v-model="filters.status" clearable placeholder="全部状态" class="filters__status">
        <el-option label="运行中" value="running" />
        <el-option label="休眠" value="sleeping" />
        <el-option label="挂起" value="suspended" />
      </el-select>
      <el-checkbox v-model="filters.onlyBlocked">仅阻塞</el-checkbox>
      <el-checkbox v-model="filters.onlyOpenTransaction">仅打开事务</el-checkbox>
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
          height="560"
          :sort-config="{ remote: true }"
          @sort-change="handleSortChange"
        >
          <vxe-column field="session_id" title="会话" width="80" sortable />
          <vxe-column field="status" title="状态" width="100" :formatter="statusFormatter" />
          <vxe-column field="login_name" title="登录名" min-width="130" show-overflow />
          <vxe-column field="host_name" title="主机" min-width="130" show-overflow />
          <vxe-column field="database_name" title="数据库" width="120" />
          <vxe-column field="open_transaction_count" title="事务" width="80" align="right" />
          <vxe-column field="cpu_time" title="CPU" width="100" align="right" sortable :formatter="numberFormatter" />
          <vxe-column field="logical_reads" title="逻辑读" width="110" align="right" sortable :formatter="numberFormatter" />
          <vxe-column field="reads" title="读" width="90" align="right" sortable :formatter="numberFormatter" />
          <vxe-column field="writes" title="写" width="90" align="right" sortable :formatter="numberFormatter" />
          <vxe-column field="wait_type" title="等待类型" width="140" show-overflow />
          <vxe-column field="wait_time_ms" title="等待" width="100" align="right" :formatter="durationFormatter" />
          <vxe-column field="blocking_session_id" title="阻塞源" width="90" />
          <vxe-column field="current_sql_preview" title="SQL 预览" min-width="260" show-overflow />
          <vxe-column title="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">详情</el-button>
              <el-button link type="danger" @click="openKill(row)">终止</el-button>
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

    <SessionDetailDrawer v-model:visible="detailVisible" :session="detail" :loading="detailLoading" :error="detailError" />
    <KillConfirmDialog v-model:visible="killVisible" :session-id="killSessionId" :loading="killLoading" @confirm="killSession" />
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref, watch } from 'vue';

import { apiClient } from '@/api/client';
import type { KillResponse, PageOut, SessionListItem } from '@/api/types';
import AutoRefreshControl from '@/components/AutoRefreshControl.vue';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import KillConfirmDialog from '@/components/KillConfirmDialog.vue';
import SessionDetailDrawer from '@/components/SessionDetailDrawer.vue';
import { useInstancesStore } from '@/stores/instances';
import { useRefreshStore } from '@/stores/refresh';
import { formatDateTime, formatDurationMs, formatNumber, formatSessionStatus } from '@/utils/format';
import { isRealtimeStale, realtimeStaleText } from '@/utils/realtimeFreshness';

const instancesStore = useInstancesStore();
const refreshStore = useRefreshStore();
const rows = ref<SessionListItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const sortBy = ref('session_id');
const sortOrder = ref<'asc' | 'desc'>('asc');
const snapshotTime = ref<string | null>(null);
const collectDelaySeconds = ref(0);
const loading = ref(false);
const error = ref('');
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailError = ref('');
const detail = ref<SessionListItem | null>(null);
const killVisible = ref(false);
const killSessionId = ref<number | null>(null);
const killLoading = ref(false);
const filters = reactive({
  status: '',
  onlyBlocked: false,
  onlyOpenTransaction: false,
});

const isStale = computed(() => {
  return isRealtimeStale(collectDelaySeconds.value);
});
const staleText = computed(() => realtimeStaleText(instancesStore.currentInstance));

async function fetchSessions() {
  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId) {
    return;
  }

  loading.value = true;
  error.value = '';
  try {
    await instancesStore.fetchInstances();
    const { data } = await apiClient.get<PageOut<SessionListItem>>('/sessions', {
      params: {
        instance_id: instanceId,
        status: filters.status || undefined,
        only_blocked: filters.onlyBlocked,
        only_open_transaction: filters.onlyOpenTransaction,
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
    error.value = '无法加载会话数据';
  } finally {
    loading.value = false;
  }
}

function resetAndFetchSessions() {
  if (page.value === 1) {
    void fetchSessions();
    return;
  }

  page.value = 1;
}

async function openDetail(row: SessionListItem) {
  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId) {
    return;
  }

  detailVisible.value = true;
  detail.value = null;
  detailError.value = '';
  detailLoading.value = true;
  try {
    const { data } = await apiClient.get<SessionListItem>(`/sessions/${row.session_id}`, {
      params: { instance_id: instanceId },
    });
    detail.value = data;
  } catch {
    detailError.value = '无法加载会话详情';
  } finally {
    detailLoading.value = false;
  }
}

function openKill(row: SessionListItem) {
  killSessionId.value = row.session_id;
  killVisible.value = true;
}

async function killSession(reason: string) {
  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId || killSessionId.value === null) {
    return;
  }

  killLoading.value = true;
  try {
    const { data } = await apiClient.post<KillResponse>('/kill', {
      instance_id: instanceId,
      session_id: killSessionId.value,
      reason,
    });
    if (data.result === 'success') {
      ElMessage.success('终止请求已提交');
    } else {
      ElMessage.warning(data.error_message || '终止请求未成功');
    }
    killVisible.value = false;
    await fetchSessions();
  } catch {
    ElMessage.error('终止会话失败');
  } finally {
    killLoading.value = false;
  }
}

function handleSortChange({ field, order }: { field: string; order: string | null }) {
  sortBy.value = field || 'session_id';
  sortOrder.value = order === 'desc' ? 'desc' : 'asc';
  resetAndFetchSessions();
}

const numberFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatNumber(cellValue);
const durationFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatDurationMs(cellValue);
const statusFormatter = ({ cellValue }: { cellValue: string | null | undefined }) => formatSessionStatus(cellValue);

onMounted(async () => {
  await instancesStore.fetchInstances();
  await fetchSessions();
});

watch(() => instancesStore.currentInstance?.id, () => {
  resetAndFetchSessions();
});
watch(() => [filters.status, filters.onlyBlocked, filters.onlyOpenTransaction], () => {
  resetAndFetchSessions();
});
watch([page, pageSize], fetchSessions);
watch(() => refreshStore.tick, fetchSessions);
</script>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}

.page__toolbar,
.filters,
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

.filters {
  display: flex;
  align-items: center;
  gap: 14px;
}

.filters__status {
  width: 160px;
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
</style>
