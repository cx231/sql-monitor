<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <AutoRefreshControl />
    </div>

    <DataState
      :loading="loading"
      :error="error"
      :empty="!blocking?.chains.length"
      :stale="isStale"
      :stale-text="staleText"
      empty-text="当前没有阻塞链路"
    >
      <template v-if="blocking">
        <div class="snapshot-line">
          快照时间：{{ formatDateTime(blocking.snapshot_time) }}，采集延迟：
          {{ blocking.collect_delay_seconds }} 秒
        </div>
        <section v-for="chain in blocking.chains" :key="`${chain.root_session_id}-${chain.max_wait_time_ms}`" class="chain">
          <div class="chain__header">
            <div>
              <strong>根阻塞：{{ chain.root_session_id ?? '未知' }}</strong>
              <span>被阻塞 {{ chain.blocked_count }} 个会话</span>
            </div>
            <div class="chain__actions">
              <el-tag :type="riskTag(chain.risk_level)" effect="plain">{{ riskText(chain.risk_level) }}</el-tag>
              <el-button
                v-if="chain.root_session_id !== null"
                link
                type="danger"
                @click="openRootKill(chain.root_session_id)"
              >
                Kill
              </el-button>
            </div>
          </div>
          <vxe-table :data="chain.nodes" size="small" border>
            <vxe-column field="chain_depth" title="层级" width="80" />
            <vxe-column field="blocking_session_id" title="阻塞源" width="100" />
            <vxe-column field="blocked_session_id" title="被阻塞会话" width="120" />
            <vxe-column field="wait_type" title="等待类型" width="160" show-overflow />
            <vxe-column field="wait_time_ms" title="等待时长" width="120" align="right" :formatter="durationFormatter" />
            <vxe-column field="resource_description" title="资源" min-width="260" show-overflow />
            <vxe-column field="cycle_detected" title="环路" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.cycle_detected" type="danger" size="small">是</el-tag>
                <span v-else>否</span>
              </template>
            </vxe-column>
          </vxe-table>
        </section>
      </template>
    </DataState>

    <KillConfirmDialog
      v-model:visible="killVisible"
      :session-id="killSessionId"
      :loading="killLoading"
      @confirm="killRootSession"
    />
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';

import { apiClient } from '@/api/client';
import type { BlockingOut, KillResponse, RiskLevel } from '@/api/types';
import AutoRefreshControl from '@/components/AutoRefreshControl.vue';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import KillConfirmDialog from '@/components/KillConfirmDialog.vue';
import { useInstancesStore } from '@/stores/instances';
import { useRefreshStore } from '@/stores/refresh';
import { formatDateTime, formatDurationMs } from '@/utils/format';
import { isRealtimeStale, realtimeStaleText } from '@/utils/realtimeFreshness';

const instancesStore = useInstancesStore();
const refreshStore = useRefreshStore();
const blocking = ref<BlockingOut | null>(null);
const loading = ref(false);
const error = ref('');
const killVisible = ref(false);
const killSessionId = ref<number | null>(null);
const killLoading = ref(false);

const isStale = computed(() => {
  return isRealtimeStale(blocking.value?.collect_delay_seconds);
});
const staleText = computed(() => realtimeStaleText(instancesStore.currentInstance));

async function fetchBlocking() {
  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId) {
    return;
  }

  loading.value = true;
  error.value = '';
  try {
    await instancesStore.fetchInstances();
    const { data } = await apiClient.get<BlockingOut>('/blocking', {
      params: { instance_id: instanceId },
    });
    blocking.value = data;
  } catch {
    error.value = '无法加载阻塞链路';
  } finally {
    loading.value = false;
  }
}

function riskText(level: RiskLevel) {
  return level === 'high' ? '高风险' : level === 'medium' ? '中风险' : '低风险';
}

function riskTag(level: RiskLevel) {
  return level === 'high' ? 'danger' : level === 'medium' ? 'warning' : 'success';
}

function openRootKill(sessionId: number) {
  killSessionId.value = sessionId;
  killVisible.value = true;
}

async function killRootSession(reason: string) {
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
    await fetchBlocking();
  } catch {
    ElMessage.error('终止根阻塞失败');
  } finally {
    killLoading.value = false;
  }
}

const durationFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatDurationMs(cellValue);

onMounted(async () => {
  await instancesStore.fetchInstances();
  await fetchBlocking();
});

watch(() => instancesStore.currentInstance?.id, fetchBlocking);
watch(() => refreshStore.tick, fetchBlocking);
</script>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}

.page__toolbar,
.chain {
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
  color: var(--app-text-secondary);
  font-size: 13px;
}

.chain {
  margin-top: 12px;
}

.chain__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.chain__actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.chain__header strong {
  margin-right: 12px;
  color: var(--app-text-primary);
}

.chain__header span {
  color: var(--app-text-secondary);
}
</style>
