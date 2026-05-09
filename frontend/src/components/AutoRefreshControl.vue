<template>
  <div class="auto-refresh">
    <el-switch v-model="enabled" active-text="自动刷新" inactive-text="暂停" />
    <el-select v-model="intervalSeconds" class="auto-refresh__interval" :disabled="!enabled">
      <el-option :value="5" label="5 秒" />
      <el-option :value="10" label="10 秒" />
      <el-option :value="30" label="30 秒" />
      <el-option :value="60" label="60 秒" />
    </el-select>
    <el-button :icon="Refresh" @click="refreshStore.requestRefresh()">刷新</el-button>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue';
import { computed, onBeforeUnmount, watch } from 'vue';

import { useRefreshStore } from '@/stores/refresh';

const refreshStore = useRefreshStore();
let timer: number | undefined;

const enabled = computed({
  get: () => refreshStore.enabled,
  set: (value: boolean) => refreshStore.setEnabled(value),
});

const intervalSeconds = computed({
  get: () => refreshStore.intervalSeconds,
  set: (value: number) => refreshStore.setIntervalSeconds(value),
});

function resetTimer() {
  if (timer) {
    window.clearInterval(timer);
    timer = undefined;
  }

  if (refreshStore.enabled) {
    timer = window.setInterval(() => {
      refreshStore.requestRefresh();
    }, refreshStore.intervalSeconds * 1000);
  }
}

watch(
  () => [refreshStore.enabled, refreshStore.intervalSeconds] as const,
  resetTimer,
  { immediate: true },
);

onBeforeUnmount(() => {
  if (timer) {
    window.clearInterval(timer);
  }
});
</script>

<style scoped>
.auto-refresh {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.auto-refresh__interval {
  width: 92px;
}
</style>
