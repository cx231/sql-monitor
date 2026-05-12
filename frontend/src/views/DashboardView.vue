<template>
  <section class="page">
    <div class="page__toolbar">
      <div class="page__toolbar-left">
        <InstanceSelector />
        <div class="window-control">
          <span class="window-control__label">曲线时长</span>
          <el-input-number
            v-model="metricsWindowMinutes"
            class="window-control__input"
            :min="1"
            :max="1440"
            :step="1"
            :controls="false"
            @change="fetchDashboard"
          />
          <span class="window-control__unit">分钟</span>
        </div>
      </div>
      <AutoRefreshControl />
    </div>

    <DataState :loading="loading && !dashboard" :error="error" :empty="!dashboard" :stale="isStale">
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

        <div class="resource-grid">
          <section v-for="item in resourceCards" :key="item.key" class="resource-panel">
            <div class="resource-panel__head">
              <div>
                <h2>{{ item.title }}</h2>
                <span>{{ item.subtitle }}</span>
              </div>
              <strong>{{ item.current }}</strong>
            </div>
            <div :ref="item.setRef" class="resource-chart" />
          </section>
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
              <vxe-column field="sql_preview" title="SQL 预览" min-width="240" show-overflow />
              <vxe-column title="操作" width="88" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openSqlDetail(row, 'CPU 最高 SQL')">详情</el-button>
                </template>
              </vxe-column>
            </vxe-table>
          </section>

          <section class="panel">
            <h2>IO 最高 SQL</h2>
            <vxe-table :data="dashboard.top_io_sqls" size="small" border height="300">
              <vxe-column field="session_id" title="会话" width="80" />
              <vxe-column field="database_name" title="数据库" width="120" />
              <vxe-column field="logical_reads" title="逻辑读" width="110" align="right" :formatter="numberFormatter" />
              <vxe-column field="writes" title="写入" width="90" align="right" :formatter="numberFormatter" />
              <vxe-column field="sql_preview" title="SQL 预览" min-width="240" show-overflow />
              <vxe-column title="操作" width="88" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openSqlDetail(row, 'IO 最高 SQL')">详情</el-button>
                </template>
              </vxe-column>
            </vxe-table>
          </section>
        </div>
      </template>
    </DataState>

    <el-dialog v-model="sqlDetailVisible" :title="sqlDetailTitle" width="860px" destroy-on-close>
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
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { VNodeRef } from 'vue';
import { ElMessage } from 'element-plus';

import { apiClient } from '@/api/client';
import type { DashboardOut, ResourceTrendPoint, SqlListItem } from '@/api/types';
import AutoRefreshControl from '@/components/AutoRefreshControl.vue';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import { useInstancesStore } from '@/stores/instances';
import { useRefreshStore } from '@/stores/refresh';
import { formatDateTime, formatDurationMs, formatNumber, formatSessionStatus, staleSeconds } from '@/utils/format';

const instancesStore = useInstancesStore();
const refreshStore = useRefreshStore();
const dashboard = ref<DashboardOut | null>(null);
const loading = ref(false);
const error = ref('');
const metricsWindowMinutes = ref(5);

const cpuChartRef = ref<HTMLDivElement | null>(null);
const memoryChartRef = ref<HTMLDivElement | null>(null);
const networkChartRef = ref<HTMLDivElement | null>(null);
const charts: Partial<Record<ResourceChartKey, echarts.ECharts>> = {};
const setCpuChartRef = setChartRef('cpu', cpuChartRef);
const setMemoryChartRef = setChartRef('memory', memoryChartRef);
const setNetworkChartRef = setChartRef('network', networkChartRef);

const sqlDetailVisible = ref(false);
const sqlDetailLoading = ref(false);
const sqlDetailError = ref('');
const sqlDetailTitle = ref('SQL 详情');
const sqlDetail = ref<SqlListItem | null>(null);

type ResourceChartKey = 'cpu' | 'memory' | 'network';

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

const latestResourcePoint = computed(() => {
  const trends = dashboard.value?.resource_trends ?? [];
  return trends.length ? trends[trends.length - 1] : null;
});

const resourceCards = computed(() => [
  {
    key: 'cpu' as const,
    title: '当前 CPU 负载',
    subtitle: `最近 ${metricsWindowMinutes.value} 分钟`,
    current: formatPercent(latestResourcePoint.value?.cpu_load_percent),
    setRef: setCpuChartRef,
  },
  {
    key: 'memory' as const,
    title: '内存使用率',
    subtitle: `最近 ${metricsWindowMinutes.value} 分钟`,
    current: formatPercent(latestResourcePoint.value?.memory_usage_percent),
    setRef: setMemoryChartRef,
  },
  {
    key: 'network' as const,
    title: '网络速率',
    subtitle: `最近 ${metricsWindowMinutes.value} 分钟`,
    current: formatNetworkRate(latestResourcePoint.value?.network_rate_bytes_per_sec),
    setRef: setNetworkChartRef,
  },
]);

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
      params: {
        instance_id: instanceId,
        metrics_window_minutes: metricsWindowMinutes.value,
      },
    });
    dashboard.value = data;
    metricsWindowMinutes.value = data.metrics_window_minutes || metricsWindowMinutes.value;
    await nextTick();
    updateCharts();
  } catch {
    error.value = '无法加载仪表盘数据';
  } finally {
    loading.value = false;
  }
}

async function openSqlDetail(row: SqlListItem, sourceTitle: string) {
  sqlDetailVisible.value = true;
  sqlDetailTitle.value = `${sourceTitle} 详情`;
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

function updateCharts() {
  const trends = dashboard.value?.resource_trends ?? [];
  renderChart('cpu', cpuChartRef.value, 'CPU 负载', trends, 'cpu_load_percent', '%');
  renderChart('memory', memoryChartRef.value, '内存使用率', trends, 'memory_usage_percent', '%');
  renderChart('network', networkChartRef.value, '网络速率', trends, 'network_rate_bytes_per_sec', 'rate');
}

function renderChart(
  key: ResourceChartKey,
  element: HTMLDivElement | null,
  name: string,
  trends: ResourceTrendPoint[],
  field: keyof Pick<ResourceTrendPoint, 'cpu_load_percent' | 'memory_usage_percent' | 'network_rate_bytes_per_sec'>,
  unit: '%' | 'rate',
) {
  if (!element) {
    return;
  }

  const chart = ensureChart(key, element);
  const xData = trends.map((point) => formatTimeLabel(point.snapshot_time));
  const seriesData = trends.map((point) => point[field]);
  const colors = readThemeColors();

  chart.setOption({
    animation: false,
    color: [key === 'cpu' ? colors.primary : key === 'memory' ? colors.success : colors.info],
    grid: { top: 16, right: 16, bottom: 26, left: 44 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: number | null | undefined) => unit === '%' ? formatPercent(value) : formatNetworkRate(value),
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xData,
      axisLine: { lineStyle: { color: colors.divider } },
      axisTick: { show: false },
      axisLabel: { color: colors.secondary, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: unit === '%' ? 100 : undefined,
      splitLine: { lineStyle: { color: colors.divider } },
      axisLabel: {
        color: colors.secondary,
        fontSize: 11,
        formatter: (value: number) => unit === '%' ? `${value}%` : compactNetworkRate(value),
      },
    },
    series: [
      {
        name,
        type: 'line',
        smooth: true,
        connectNulls: false,
        symbolSize: 5,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.12 },
        data: seriesData,
      },
    ],
  });
}

function ensureChart(key: ResourceChartKey, element: HTMLDivElement) {
  const chart = charts[key];
  if (chart && chart.getDom() !== element) {
    disposeChart(key);
  }

  if (!charts[key]) {
    charts[key] = echarts.init(element);
  }
  return charts[key];
}

function setChartRef(key: ResourceChartKey, target: typeof cpuChartRef): VNodeRef {
  return (element) => {
    target.value = element instanceof HTMLDivElement ? element : null;
    if (!target.value) {
      disposeChart(key);
    }
  };
}

function resizeCharts() {
  Object.values(charts).forEach((chart) => chart?.resize());
}

function disposeChart(key: ResourceChartKey) {
  charts[key]?.dispose();
  delete charts[key];
}

function disposeCharts() {
  (Object.keys(charts) as ResourceChartKey[]).forEach(disposeChart);
}

function readThemeColors() {
  const styles = getComputedStyle(document.documentElement);
  return {
    primary: styles.getPropertyValue('--app-primary').trim(),
    success: styles.getPropertyValue('--app-success').trim(),
    info: styles.getPropertyValue('--app-info').trim(),
    divider: styles.getPropertyValue('--app-divider').trim(),
    secondary: styles.getPropertyValue('--app-text-secondary').trim(),
  };
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-';
  }
  return `${value.toFixed(1)}%`;
}

function formatNetworkRate(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-';
  }
  if (value >= 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(2)} MB/s`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} KB/s`;
  }
  return `${value.toFixed(0)} B/s`;
}

function compactNetworkRate(value: number) {
  if (value >= 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(1)}M`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(0)}K`;
  }
  return `${value.toFixed(0)}`;
}

function formatTimeLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

const numberFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatNumber(cellValue);
const durationFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatDurationMs(cellValue);

onMounted(async () => {
  await instancesStore.fetchInstances();
  await fetchDashboard();
  window.addEventListener('resize', resizeCharts);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts);
  disposeCharts();
});

watch(() => instancesStore.currentInstance?.id, fetchDashboard);
watch(() => refreshStore.tick, fetchDashboard);
watch(() => document.documentElement.dataset.theme, () => {
  nextTick(updateCharts);
});
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
  background: var(--app-surface);
  border: 1px solid var(--app-divider);
  border-radius: 6px;
}

.page__toolbar-left,
.window-control {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.window-control {
  padding-left: 12px;
  border-left: 1px solid var(--app-divider);
}

.window-control__label,
.window-control__unit {
  color: var(--app-text-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.window-control__input {
  width: 86px;
}

.snapshot-line {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(120px, 1fr));
  gap: 10px;
}

.metric-card,
.resource-panel,
.panel {
  background: var(--app-surface);
  border: 1px solid var(--app-divider);
  border-radius: 6px;
}

.metric-card {
  padding: 12px;
}

.metric-card span {
  display: block;
  color: var(--app-text-secondary);
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin-top: 8px;
  color: var(--app-text-primary);
  font-size: 24px;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.resource-panel {
  min-width: 0;
  padding: 12px;
}

.resource-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.resource-panel h2,
.panel h2 {
  margin: 0;
  color: var(--app-text-primary);
  font-size: 16px;
}

.resource-panel__head span {
  display: block;
  margin-top: 4px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.resource-panel__head strong {
  color: var(--app-text-primary);
  font-size: 22px;
  line-height: 1.2;
  white-space: nowrap;
}

.resource-chart {
  width: 100%;
  height: 180px;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.panel {
  min-width: 0;
  padding: 12px;
}

.panel h2 {
  margin-bottom: 10px;
}

.panel:nth-child(3) {
  grid-column: 1 / -1;
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

@media (max-width: 1200px) {
  .metric-grid {
    grid-template-columns: repeat(3, minmax(120px, 1fr));
  }

  .resource-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .page__toolbar,
  .page__toolbar-left {
    align-items: stretch;
    flex-direction: column;
  }

  .window-control {
    justify-content: flex-start;
    padding-left: 0;
    border-left: 0;
  }

  .metric-grid,
  .sql-detail__grid {
    grid-template-columns: 1fr;
  }
}
</style>
