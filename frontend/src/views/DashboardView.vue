<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <AutoRefreshControl />
    </div>

    <DataState :loading="loading" :error="error" :empty="!dashboard" :stale="isStale">
      <template v-if="dashboard">
        <div class="snapshot-line">
          快照时间：{{ formatDateTime(dashboard.snapshot_time) }}，采集延迟：
          {{ dashboard.collect_delay_seconds }} 秒
        </div>

        <div class="metric-grid">
          <div v-for="item in metrics" :key="item.label" class="metric-card">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>

        <div class="content-grid">
          <section class="panel">
            <h2>主要等待</h2>
            <vxe-table :data="dashboard.top_waits" size="small" border height="300">
              <vxe-column field="wait_type" title="等待类型" min-width="160" />
              <vxe-column field="wait_category" title="类别" width="120" />
              <vxe-column field="waiting_tasks_count" title="任务数" width="90" align="right" />
              <vxe-column field="total_wait_time_ms" title="总等待" width="110" align="right" :formatter="durationFormatter" />
              <vxe-column field="max_wait_time_ms" title="最长等待" width="110" align="right" :formatter="durationFormatter" />
            </vxe-table>
          </section>

          <section class="panel">
            <h2>CPU 最高 SQL</h2>
            <vxe-table :data="dashboard.top_cpu_sqls" size="small" border height="300">
              <vxe-column field="session_id" title="会话" width="80" />
              <vxe-column field="database_name" title="数据库" width="120" />
              <vxe-column field="cpu_time_ms" title="CPU" width="100" align="right" :formatter="numberFormatter" />
              <vxe-column field="duration_ms" title="耗时" width="100" align="right" :formatter="durationFormatter" />
              <vxe-column field="sql_preview" title="SQL 预览" min-width="260" show-overflow />
            </vxe-table>
          </section>

          <section class="panel">
            <h2>IO 最高 SQL</h2>
            <vxe-table :data="dashboard.top_io_sqls" size="small" border height="300">
              <vxe-column field="session_id" title="会话" width="80" />
              <vxe-column field="database_name" title="数据库" width="120" />
              <vxe-column field="logical_reads" title="逻辑读" width="110" align="right" :formatter="numberFormatter" />
              <vxe-column field="writes" title="写入" width="90" align="right" :formatter="numberFormatter" />
              <vxe-column field="sql_preview" title="SQL 预览" min-width="260" show-overflow />
            </vxe-table>
          </section>
        </div>
      </template>
    </DataState>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import { apiClient } from '@/api/client';
import type { DashboardOut } from '@/api/types';
import AutoRefreshControl from '@/components/AutoRefreshControl.vue';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import { useInstancesStore } from '@/stores/instances';
import { useRefreshStore } from '@/stores/refresh';
import { formatDateTime, formatDurationMs, formatNumber, staleSeconds } from '@/utils/format';

const instancesStore = useInstancesStore();
const refreshStore = useRefreshStore();
const dashboard = ref<DashboardOut | null>(null);
const loading = ref(false);
const error = ref('');

const metrics = computed(() => {
  const data = dashboard.value?.metrics;
  if (!data) {
    return [];
  }

  return [
    { label: '总会话', value: formatNumber(data.session_count) },
    { label: '活动请求', value: formatNumber(data.active_request_count) },
    { label: '阻塞会话', value: formatNumber(data.blocked_session_count) },
    { label: '根阻塞', value: formatNumber(data.root_blocker_count) },
    { label: '最长阻塞', value: formatDurationMs(data.max_blocking_duration_ms) },
    { label: '等待请求', value: formatNumber(data.waiting_request_count) },
    { label: '近 1 小时死锁', value: formatNumber(data.deadlocks_last_hour) },
  ];
});

const isStale = computed(() => {
  const seconds = staleSeconds(dashboard.value?.snapshot_time);
  return seconds !== null && seconds > 60;
});

async function fetchDashboard() {
  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId) {
    return;
  }

  loading.value = true;
  error.value = '';
  try {
    const { data } = await apiClient.get<DashboardOut>('/dashboard', {
      params: { instance_id: instanceId },
    });
    dashboard.value = data;
  } catch {
    error.value = '无法加载仪表盘数据';
  } finally {
    loading.value = false;
  }
}

const numberFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatNumber(cellValue);
const durationFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatDurationMs(cellValue);

onMounted(async () => {
  await instancesStore.fetchInstances();
  await fetchDashboard();
});

watch(() => instancesStore.currentInstance?.id, fetchDashboard);
watch(() => refreshStore.tick, fetchDashboard);
</script>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}

.page__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.snapshot-line {
  color: #606266;
  font-size: 13px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(120px, 1fr));
  gap: 10px;
}

.metric-card {
  padding: 12px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.metric-card span {
  display: block;
  color: #606266;
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin-top: 8px;
  color: #1f2937;
  font-size: 24px;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.panel {
  min-width: 0;
  padding: 12px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.panel h2 {
  margin: 0 0 10px;
  color: #1f2937;
  font-size: 16px;
}

.panel:nth-child(3) {
  grid-column: 1 / -1;
}

@media (max-width: 1200px) {
  .metric-grid {
    grid-template-columns: repeat(3, minmax(120px, 1fr));
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
