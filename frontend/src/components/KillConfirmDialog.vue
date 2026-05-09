<template>
  <el-dialog
    :model-value="visible"
    title="终止会话确认"
    width="460px"
    destroy-on-close
    @close="handleClose"
  >
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="该操作会向 SQL Server 发送 KILL 命令，请确认影响范围。"
    />

    <el-form class="kill-dialog__form" label-position="top">
      <el-form-item label="目标会话 ID">
        <el-input :model-value="String(sessionId ?? '-')" disabled />
      </el-form-item>
      <el-form-item label="原因">
        <el-input
          v-model="reason"
          type="textarea"
          :rows="4"
          maxlength="200"
          show-word-limit
          placeholder="请输入终止原因"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="danger" :loading="loading" :disabled="!reason.trim()" @click="confirm">
        确认终止
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';

const props = defineProps<{
  visible: boolean;
  sessionId: number | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
  confirm: [reason: string];
}>();

const reason = ref('');

function handleClose() {
  emit('update:visible', false);
}

function confirm() {
  const value = reason.value.trim();
  if (value) {
    emit('confirm', value);
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      reason.value = '';
    }
  },
);
</script>

<style scoped>
.kill-dialog__form {
  margin-top: 14px;
}
</style>
