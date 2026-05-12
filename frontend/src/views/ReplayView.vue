<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <div class="replay-controls">
        <el-date-picker
          v-model="selectedTime"
          type="datetime"
          placeholder="选择回放时间"
          value-format="YYYY-MM-DDTHH:mm:ss"
        />
        <el-button type="primary" @click="fetchReplay">查询回放</el-button>
      </div>
    </div>

    <DataState :loading="loading" :error="error" :empty="!frame" empty-text="请选择时间查询历史快照">
      <template v-if="frame">
        <div class="snapshot-line">
          请求时间：{{ formatDateTime(frame.requested_time) }}，命中快照：{{ formatDateTime(frame.snapshot_time) }}
        </div>

        <div class="metric-grid">
          <div class="metric-card">
            <span>总会话</span>
            <strong>{{ formatNumber(frame.dashboard.metrics.session_count) }}</strong>
          </div>
          <div class="metric-card">
            <span>活动请求</span>
            <strong>{{ formatNumber(frame.dashboard.metrics.active_request_count) }}</strong>
          </div>
          <div class="metric-card">
            <span>阻塞会话</span>
            <strong>{{ formatNumber(frame.dashboard.metrics.blocked_session_count) }}</strong>
          </div>
          <div class="metric-card">
            <span>根阻塞</span>
            <strong>{{ formatNumber(frame.dashboard.metrics.root_blocker_count) }}</strong>
          </div>
        </div>

        <el-tabs class="replay-tabs">
          <el-tab-pane label="会话" name="sessions">
            <vxe-table :data="frame.sessions" size="small" border height="320">
              <vxe-column field="session_id" title="会话" width="80" />
              <vxe-column field="status" title="状态" width="100" :formatter="statusFormatter" />
              <vxe-column field="login_name" title="登录名" min-width="130" show-overflow />
              <vxe-column field="database_name" title="数据库" width="120" />
              <vxe-column field="wait_type" title="等待类型" width="140" show-overflow />
              <vxe-column field="current_sql_preview" title="SQL 预览" min-width="300" show-overflow />
            </vxe-table>
          </el-tab-pane>
          <el-tab-pane label="SQL" name="sqls">
            <vxe-table :data="frame.sqls" size="small" border height="320">
              <vxe-column field="session_id" title="会话" width="80" />
              <vxe-column field="cpu_time_ms" title="CPU" width="110" align="right" :formatter="numberFormatter" />
              <vxe-column field="logical_reads" title="逻辑读" width="120" align="right" :formatter="numberFormatter" />
              <vxe-column field="wait_time_ms" title="等待" width="110" align="right" :formatter="durationFormatter" />
              <vxe-column field="sql_preview" title="SQL 预览" min-width="360" show-overflow />
            </vxe-table>
          </el-tab-pane>
          <el-tab-pane label="阻塞" name="blocking">
            <section v-for="chain in frame.blocking" :key="`${chain.root_session_id}-${chain.max_wait_time_ms}`" class="chain">
              根阻塞 {{ chain.root_session_id ?? '未知' }}，被阻塞 {{ chain.blocked_count }} 个会话，最长等待
              {{ formatDurationMs(chain.max_wait_time_ms) }}
            </section>
          </el-tab-pane>
        </el-tabs>
      </template>
    </DataState>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';

import { apiClient } from '@/api/client';
import type { ReplayFrameOut } from '@/api/types';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import { useInstancesStore } from '@/stores/instances';
import { formatDateTime, formatDurationMs, formatNumber, formatSessionStatus } from '@/utils/format';

const instancesStore = useInstancesStore();
const frame = ref<ReplayFrameOut | null>(null);
const selectedTime = ref('');
const loading = ref(false);
const error = ref('');

async function fetchReplay() {
  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId || !selectedTime.value) {
    return;
  }

  loading.value = true;
  error.value = '';
  try {
    const { data } = await apiClient.get<ReplayFrameOut>('/replay', {
      params: {
        instance_id: instanceId,
        time: selectedTime.value,
      },
    });
    frame.value = data;
  } catch {
    error.value = '无法加载回放快照';
  } finally {
    loading.value = false;
  }
}

const numberFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatNumber(cellValue);
const durationFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatDurationMs(cellValue);
const statusFormatter = ({ cellValue }: { cellValue: string | null | undefined }) => formatSessionStatus(cellValue);

onMounted(async () => {
  await instancesStore.fetchInstances();
});

watch(() => instancesStore.currentInstance?.id, () => {
  frame.value = null;
});
</script>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}

.page__toolbar,
.replay-tabs {
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

.replay-controls {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.snapshot-line {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(140px, 1fr));
  gap: 10px;
}

.metric-card {
  padding: 12px;
  background: var(--app-surface);
  border: 1px solid var(--app-divider);
  border-radius: 6px;
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
  font-size: 22px;
}

.chain {
  padding: 10px 12px;
  border-bottom: 1px solid var(--app-divider);
  color: var(--app-text-primary);
}
</style>
