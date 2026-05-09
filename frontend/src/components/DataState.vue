<template>
  <div v-if="loading" class="data-state">
    <el-icon class="is-loading"><Loading /></el-icon>
    <span>{{ loadingText }}</span>
  </div>

  <template v-else>
    <el-alert
      v-if="error"
      class="data-state__alert"
      type="error"
      :title="errorTitle"
      :description="error"
      show-icon
      :closable="false"
    />

    <template v-else>
      <el-alert
        v-if="stale"
        class="data-state__alert"
        type="warning"
        :title="staleTitle"
        :description="staleText"
        show-icon
        :closable="false"
      />

      <el-empty v-if="empty" class="data-state__empty" :description="emptyText" />

      <slot v-else />
    </template>
  </template>
</template>

<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue';

defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  empty: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
  stale: {
    type: Boolean,
    default: false,
  },
  loadingText: {
    type: String,
    default: '正在加载数据...',
  },
  emptyText: {
    type: String,
    default: '暂无数据',
  },
  errorTitle: {
    type: String,
    default: '数据加载失败',
  },
  staleTitle: {
    type: String,
    default: '数据可能已过期',
  },
  staleText: {
    type: String,
    default: '当前快照时间较早，请检查采集状态或手动刷新。',
  },
});
</script>

<style scoped>
.data-state {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #606266;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.data-state__alert {
  margin-bottom: 12px;
}

.data-state__empty {
  min-height: 180px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}
</style>
