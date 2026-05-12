<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <AutoRefreshControl />
    </div>

    <DataState :loading="loading" :error="error" :empty="!blocking?.chains.length" :stale="isStale" empty-text="当前没有阻塞链路">
      <template v-if="blocking">
        <div class="snapshot-line">快照时间：{{ formatDateTime(blocking.snapshot_time) }}</div>
        <section v-for="chain in blocking.chains" :key="`${chain.root_session_id}-${chain.max_wait_time_ms}`" class="chain">
          <div class="chain__header">
            <div>
              <strong>根阻塞：{{ chain.root_session_id ?? '未知' }}</strong>
              <span>被阻塞 {{ chain.blocked_count }} 个会话</span>
            </div>
            <el-tag :type="riskTag(chain.risk_level)" effect="plain">{{ riskText(chain.risk_level) }}</el-tag>
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
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import { apiClient } from '@/api/client';
import type { BlockingOut, RiskLevel } from '@/api/types';
import AutoRefreshControl from '@/components/AutoRefreshControl.vue';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import { useInstancesStore } from '@/stores/instances';
import { useRefreshStore } from '@/stores/refresh';
import { formatDateTime, formatDurationMs, staleSeconds } from '@/utils/format';

const instancesStore = useInstancesStore();
const refreshStore = useRefreshStore();
const blocking = ref<BlockingOut | null>(null);
const loading = ref(false);
const error = ref('');

const isStale = computed(() => {
  const seconds = staleSeconds(blocking.value?.snapshot_time);
  return seconds !== null && seconds > 60;
});

async function fetchBlocking() {
  const instanceId = instancesStore.currentInstance?.id;
  if (!instanceId) {
    return;
  }

  loading.value = true;
  error.value = '';
  try {
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
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.chain__header strong {
  margin-right: 12px;
  color: var(--app-text-primary);
}

.chain__header span {
  color: var(--app-text-secondary);
}
</style>
