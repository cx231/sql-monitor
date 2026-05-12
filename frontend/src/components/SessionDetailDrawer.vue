<template>
  <el-drawer
    :model-value="visible"
    title="会话详情"
    size="520px"
    destroy-on-close
    @close="$emit('update:visible', false)"
  >
    <DataState :loading="loading" :error="error" :empty="!session" empty-text="未找到会话">
      <template v-if="session">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="会话 ID">{{ session.session_id }}</el-descriptions-item>
          <el-descriptions-item label="登录名">{{ formatNullable(session.login_name) }}</el-descriptions-item>
          <el-descriptions-item label="主机">{{ formatNullable(session.host_name) }}</el-descriptions-item>
          <el-descriptions-item label="程序">{{ formatNullable(session.program_name) }}</el-descriptions-item>
          <el-descriptions-item label="数据库">{{ formatNullable(session.database_name) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ formatSessionStatus(session.status) }}</el-descriptions-item>
          <el-descriptions-item label="打开事务">{{ session.open_transaction_count }}</el-descriptions-item>
          <el-descriptions-item label="CPU">{{ formatNumber(session.cpu_time) }}</el-descriptions-item>
          <el-descriptions-item label="逻辑读">{{ formatNumber(session.logical_reads) }}</el-descriptions-item>
          <el-descriptions-item label="物理读">{{ formatNumber(session.reads) }}</el-descriptions-item>
          <el-descriptions-item label="写入">{{ formatNumber(session.writes) }}</el-descriptions-item>
          <el-descriptions-item label="等待类型">{{ formatNullable(session.wait_type) }}</el-descriptions-item>
          <el-descriptions-item label="等待时长">{{ formatDurationMs(session.wait_time_ms) }}</el-descriptions-item>
          <el-descriptions-item label="阻塞源">{{ formatNullable(session.blocking_session_id) }}</el-descriptions-item>
        </el-descriptions>

        <div class="session-detail__sql">
          <div class="session-detail__title">当前 SQL</div>
          <pre>{{ session.current_sql_preview || '暂无 SQL 文本' }}</pre>
        </div>
      </template>
    </DataState>
  </el-drawer>
</template>

<script setup lang="ts">
import DataState from '@/components/DataState.vue';
import type { SessionListItem } from '@/api/types';
import { formatDurationMs, formatNullable, formatNumber, formatSessionStatus } from '@/utils/format';

defineProps<{
  visible: boolean;
  session: SessionListItem | null;
  loading: boolean;
  error: string;
}>();

defineEmits<{
  'update:visible': [value: boolean];
}>();
</script>

<style scoped>
.session-detail__sql {
  margin-top: 16px;
}

.session-detail__title {
  margin-bottom: 8px;
  color: var(--app-text-primary);
  font-weight: 600;
}

.session-detail__sql pre {
  max-height: 260px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  color: var(--app-text-primary);
  background: var(--app-surface-muted);
  border: 1px solid var(--app-divider);
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
