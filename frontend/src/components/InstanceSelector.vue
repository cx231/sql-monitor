<template>
  <div class="instance-selector">
    <span class="instance-selector__label">实例</span>
    <el-select
      v-model="selectedId"
      class="instance-selector__select"
      filterable
      :loading="store.loading"
      placeholder="选择实例"
      @visible-change="handleVisibleChange"
    >
      <el-option
        v-for="instance in store.items"
        :key="instance.id"
        :label="`${instance.name} (${instance.host}:${instance.port})`"
        :value="instance.id"
      >
        <div class="instance-selector__option">
          <span>{{ instance.name }}</span>
          <small>{{ instance.environment }} · {{ instance.host }}:{{ instance.port }}</small>
        </div>
      </el-option>
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';

import { useInstancesStore } from '@/stores/instances';

const store = useInstancesStore();

const selectedId = computed({
  get: () => store.currentInstance?.id ?? null,
  set: (value: string | null) => store.setCurrentInstance(value),
});

function handleVisibleChange(visible: boolean) {
  if (visible && store.items.length === 0) {
    void store.fetchInstances();
  }
}

onMounted(() => {
  if (store.items.length === 0) {
    void store.fetchInstances();
  }
});
</script>

<style scoped>
.instance-selector {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.instance-selector__label {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.instance-selector__select {
  width: 300px;
}

.instance-selector__option {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.instance-selector__option small {
  color: var(--app-text-disabled);
}
</style>
