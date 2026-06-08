<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <div class="database-selector">
        <span class="database-selector__label">用户库</span>
        <el-select
          v-model="selectedDatabase"
          class="database-selector__select"
          filterable
          :loading="databasesLoading"
          :disabled="!currentInstanceId"
          placeholder="选择用户库"
        >
          <el-option
            v-for="database in databases"
            :key="database"
            :label="database"
            :value="database"
          />
        </el-select>
      </div>
      <el-button
        type="primary"
        :icon="Refresh"
        :disabled="!selectedDatabase || fragmentationLoading"
        :loading="fragmentationLoading"
        @click="refreshFragmentation"
      >
        刷新
      </el-button>
    </div>

    <div v-if="selectedDatabase" class="snapshot-panel">
      <div class="snapshot-line">
        快照最后更新时间：{{ snapshotUpdatedAtText }}
        <el-tag class="online-tag" :type="collectionStatusTag" effect="plain">
          {{ collectionStatusText }}
        </el-tag>
        <el-tag class="online-tag" :type="onlineRebuildSupported ? 'success' : 'info'" effect="plain">
          {{ onlineRebuildSupported ? '支持 Online Rebuild' : '不支持 Online Rebuild' }}
        </el-tag>
      </div>
      <el-alert
        v-if="collectionNotice"
        class="snapshot-alert"
        :type="collectionNoticeType"
        :title="collectionNotice"
        :closable="false"
        show-icon
      />
    </div>

    <DataState
      :loading="databasesLoading || (fragmentationLoading && !rows.length)"
      :error="error"
      :empty="!selectedDatabase || !rows.length"
      :empty-text="emptyText"
      loading-text="正在加载索引碎片快照..."
    >
      <div v-loading="fragmentationLoading" class="table-panel" element-loading-text="正在加载索引碎片快照...">
        <vxe-table :data="rows" size="small" border height="620">
          <vxe-column field="schema_name" title="Schema" width="110" />
          <vxe-column field="table_name" title="表名" min-width="170" show-overflow />
          <vxe-column field="index_name" title="索引名" min-width="240" show-overflow />
          <vxe-column field="index_type" title="类型" width="150" show-overflow />
          <vxe-column field="partition_number" title="分区" width="80" align="right" />
          <vxe-column field="avg_fragmentation_in_percent" title="碎片率" width="110" align="right" :formatter="percentFormatter" />
          <vxe-column field="page_count" title="页数" width="110" align="right" :formatter="numberFormatter" />
          <vxe-column title="建议" width="130">
            <template #default="{ row }">
              <el-tag :type="actionTag(row.recommended_action)" effect="plain">
                {{ actionText(row.recommended_action) }}
              </el-tag>
            </template>
          </vxe-column>
          <vxe-column title="操作" width="170" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.action_enabled"
                link
                type="primary"
                @click="openActionDialog(row)"
              >
                执行 {{ row.recommended_action }}
              </el-button>
              <span v-else class="muted-text">不处理</span>
            </template>
          </vxe-column>
        </vxe-table>
        <div class="pagination-line">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            background
            layout="total, sizes, prev, pager, next"
            :page-sizes="[20, 50, 100, 200, 500]"
            :pager-count="5"
            :total="total"
            :disabled="fragmentationLoading"
            @current-change="handlePageChange"
            @size-change="handlePageSizeChange"
          />
        </div>
      </div>
    </DataState>

    <el-dialog v-model="actionVisible" title="执行索引维护" width="560px" destroy-on-close>
      <template v-if="actionTarget">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          :title="actionAlertTitle"
        />
        <el-form class="action-dialog__form" label-position="top">
          <el-form-item label="目标">
            <el-input :model-value="targetLabel" disabled />
          </el-form-item>
          <el-form-item label="动作">
            <el-input :model-value="actionDescription" disabled />
          </el-form-item>
          <el-form-item label="碎片率 / 页数">
            <el-input :model-value="`${formatPercent(actionTarget.avg_fragmentation_in_percent)} / ${formatNumber(actionTarget.page_count)}`" disabled />
          </el-form-item>
        </el-form>
      </template>

      <template #footer>
        <el-button @click="actionVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="executeAction">
          确认执行
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import axios from 'axios';
import { Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';

import { INDEX_OPERATION_TIMEOUT_MS, apiClient } from '@/api/client';
import type {
  IndexDatabaseListOut,
  IndexFragmentationAction,
  IndexFragmentationActionResponse,
  IndexAuditOut,
  IndexFragmentationItem,
  IndexFragmentationListOut,
} from '@/api/types';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import { useInstancesStore } from '@/stores/instances';
import { formatNumber } from '@/utils/format';
import { formatSnapshotDateTime } from '@/utils/format';

const instancesStore = useInstancesStore();
const databases = ref<string[]>([]);
const selectedDatabase = ref<string | null>(null);
const rows = ref<IndexFragmentationItem[]>([]);
const checkedAt = ref<string | null>(null);
const collectionStatus = ref('unknown');
const collectionError = ref<string | null>(null);
const stale = ref(true);
const onlineRebuildSupported = ref(false);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const databasesLoading = ref(false);
const fragmentationLoading = ref(false);
const actionLoading = ref(false);
const error = ref('');
const actionVisible = ref(false);
const actionTarget = ref<IndexFragmentationItem | null>(null);
let fragmentationRequestSeq = 0;
let fragmentationAbortController: AbortController | null = null;
const AUDIT_POLL_INTERVAL_MS = 2000;
const AUDIT_POLL_ATTEMPTS = 10;

const currentInstanceId = computed(() => instancesStore.currentInstance?.id ?? null);
const emptyText = computed(() => {
  if (!selectedDatabase.value) {
    return '请选择用户库';
  }
  return '当前用户库暂无索引碎片数据';
});
const collectionStatusText = computed(() => {
  if (collectionStatus.value === 'success') {
    return stale.value ? '数据可能过期' : '采集成功';
  }
  if (collectionStatus.value === 'failed') {
    return '采集失败';
  }
  return '等待采集';
});
const collectionStatusTag = computed(() => {
  if (collectionStatus.value === 'failed') {
    return 'danger';
  }
  if (stale.value) {
    return 'warning';
  }
  if (collectionStatus.value === 'success') {
    return 'success';
  }
  return 'info';
});
const collectionNotice = computed(() => {
  if (collectionError.value) {
    return collectionError.value;
  }
  if (!checkedAt.value) {
    return '等待 collector 采集索引碎片数据';
  }
  if (stale.value) {
    return '本地索引碎片快照可能已过期，请确认 collector 运行状态';
  }
  return '';
});
const collectionNoticeType = computed(() => (collectionStatus.value === 'failed' ? 'error' : 'warning'));
const snapshotUpdatedAtText = computed(() => formatSnapshotDateTime(checkedAt.value));
const targetLabel = computed(() => {
  const target = actionTarget.value;
  if (!target) {
    return '-';
  }
  return `${target.database_name}.${target.schema_name}.${target.table_name}.${target.index_name}`;
});
const actionDescription = computed(() => {
  const target = actionTarget.value;
  if (!target) {
    return '-';
  }
  if (target.recommended_action === 'REBUILD' && target.online_rebuild_supported) {
    return 'REBUILD WITH (ONLINE = ON)';
  }
  return target.recommended_action;
});
const actionAlertTitle = computed(() => {
  const target = actionTarget.value;
  if (target?.recommended_action === 'REBUILD' && target.online_rebuild_supported) {
    return '该操作会执行 ALTER INDEX REBUILD，并使用 ONLINE = ON。';
  }
  return '该操作会在 SQL Server 中执行索引维护，请确认目标索引和动作。';
});

async function fetchDatabases() {
  const instanceId = currentInstanceId.value;
  databases.value = [];
  selectedDatabase.value = null;
  rows.value = [];
  checkedAt.value = null;
  collectionStatus.value = 'unknown';
  collectionError.value = null;
  stale.value = true;
  onlineRebuildSupported.value = false;
  page.value = 1;
  total.value = 0;
  if (!instanceId) {
    return;
  }

  databasesLoading.value = true;
  error.value = '';
  try {
    const { data } = await apiClient.get<IndexDatabaseListOut>('/indexes/databases', {
      params: { instance_id: instanceId },
    });
    databases.value = data.databases;
    selectedDatabase.value = data.databases[0] ?? null;
  } catch (fetchError) {
    error.value = requestMessage(fetchError, '无法加载用户库列表');
  } finally {
    databasesLoading.value = false;
  }
}

async function fetchFragmentation() {
  const instanceId = currentInstanceId.value;
  const databaseName = selectedDatabase.value;
  if (!instanceId || !databaseName) {
    return;
  }

  fragmentationLoading.value = true;
  error.value = '';
  const requestSeq = ++fragmentationRequestSeq;
  fragmentationAbortController?.abort();
  fragmentationAbortController = new AbortController();
  try {
    const { data } = await apiClient.get<IndexFragmentationListOut>('/indexes/fragmentation', {
      params: {
        instance_id: instanceId,
        database_name: databaseName,
        page: page.value,
        page_size: pageSize.value,
      },
      signal: fragmentationAbortController.signal,
    });
    if (requestSeq !== fragmentationRequestSeq) {
      return;
    }
    rows.value = data.items.slice(0, pageSize.value);
    checkedAt.value = data.checked_at;
    collectionStatus.value = data.collection_status;
    collectionError.value = data.collection_error;
    stale.value = data.stale;
    onlineRebuildSupported.value = data.online_rebuild_supported;
    page.value = data.page;
    pageSize.value = data.page_size;
    total.value = data.total;
  } catch (fetchError) {
    if (axios.isCancel(fetchError)) {
      return;
    }
    if (requestSeq !== fragmentationRequestSeq) {
      return;
    }
    rows.value = [];
    checkedAt.value = null;
    collectionStatus.value = 'failed';
    collectionError.value = requestMessage(fetchError, '无法加载索引碎片本地快照');
    stale.value = true;
    onlineRebuildSupported.value = false;
    total.value = 0;
    error.value = collectionError.value;
  } finally {
    if (requestSeq === fragmentationRequestSeq) {
      fragmentationLoading.value = false;
      fragmentationAbortController = null;
    }
  }
}

async function refreshFragmentation() {
  page.value = 1;
  await fetchFragmentation();
}

async function handlePageSizeChange() {
  page.value = 1;
  await fetchFragmentation();
}

async function handlePageChange() {
  await fetchFragmentation();
}

function openActionDialog(row: IndexFragmentationItem) {
  actionTarget.value = row;
  actionVisible.value = true;
}

async function executeAction() {
  const instanceId = currentInstanceId.value;
  const target = actionTarget.value;
  if (!instanceId || !target || target.recommended_action === 'NONE') {
    return;
  }

  actionLoading.value = true;
  try {
    const { data } = await apiClient.post<IndexFragmentationActionResponse>(
      '/indexes/fragmentation/actions',
      {
        instance_id: instanceId,
        database_name: target.database_name,
        schema_name: target.schema_name,
        table_name: target.table_name,
        index_name: target.index_name,
        partition_number: target.partition_number,
        action: target.recommended_action,
        avg_fragmentation_in_percent: target.avg_fragmentation_in_percent,
        page_count: target.page_count,
      },
      { timeout: INDEX_OPERATION_TIMEOUT_MS },
    );
    if (data.result === 'success') {
      ElMessage.success(data.online_used ? '索引维护已执行，使用 ONLINE = ON' : '索引维护已执行');
      actionVisible.value = false;
      await refreshFragmentation();
      return;
    }
    if (data.result === 'running') {
      ElMessage.success('索引维护已提交后台执行，请稍后刷新确认结果');
      actionVisible.value = false;
      void pollIndexAudit(data.audit_id);
      return;
    }
    ElMessage.warning(data.error_message || '索引维护未成功');
  } catch (actionError) {
    const message = requestMessage(actionError, '索引维护失败');
    if (message === 'OPERATION_DSN_NOT_CONFIGURED') {
      ElMessage.error('未配置可执行数据库连接，无法执行索引维护');
    } else if (message === 'INDEX_MAINTENANCE_TIMEOUT') {
      ElMessage.error('索引维护执行超时，请检查目标表大小、锁等待或稍后重试');
    } else if (message === 'CLIENT_TIMEOUT') {
      ElMessage.error('前端等待索引维护超时，后台可能仍在执行，请稍后刷新确认结果');
    } else {
      ElMessage.error(message);
    }
  } finally {
    actionLoading.value = false;
  }
}

async function pollIndexAudit(auditId: string) {
  for (let attempt = 0; attempt < AUDIT_POLL_ATTEMPTS; attempt += 1) {
    await delay(AUDIT_POLL_INTERVAL_MS);
    try {
      const { data } = await apiClient.get<IndexAuditOut>(`/indexes/audits/${auditId}`);
      if (data.result === 'running') {
        continue;
      }
      if (data.result === 'success') {
        ElMessage.success('索引维护完成');
        await refreshFragmentation();
        return;
      }
      ElMessage.error(indexAuditErrorText(data.error_message, '索引维护失败'));
      return;
    } catch {
      return;
    }
  }
  ElMessage.info('索引维护仍在后台执行，请稍后刷新确认结果');
}

function delay(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function indexAuditErrorText(message: string | null, fallback: string) {
  if (message === 'INDEX_MAINTENANCE_TIMEOUT') {
    return '索引维护执行超时，请检查目标表大小、锁等待或稍后重试';
  }
  if (message === 'INDEX_MAINTENANCE_FAILED') {
    return fallback;
  }
  return message || fallback;
}

function actionText(action: IndexFragmentationAction) {
  return action === 'NONE' ? '不处理' : action;
}

function actionTag(action: IndexFragmentationAction) {
  if (action === 'REBUILD') {
    return 'danger';
  }
  if (action === 'REORGANIZE') {
    return 'warning';
  }
  return 'info';
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-';
  }
  return `${value.toFixed(1)}%`;
}

function requestMessage(errorValue: unknown, fallback: string) {
  if (axios.isAxiosError(errorValue)) {
    if (errorValue.code === 'ECONNABORTED') {
      return 'CLIENT_TIMEOUT';
    }
    const detail = errorValue.response?.data?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  return fallback;
}

const numberFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatNumber(cellValue);
const percentFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => formatPercent(cellValue);

onMounted(async () => {
  await instancesStore.fetchInstances();
  await fetchDatabases();
});

watch(currentInstanceId, fetchDatabases);
watch(selectedDatabase, () => {
  rows.value = [];
  checkedAt.value = null;
  collectionStatus.value = 'unknown';
  collectionError.value = null;
  stale.value = true;
  onlineRebuildSupported.value = false;
  page.value = 1;
  total.value = 0;
  void fetchFragmentation();
});
</script>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}

.page__toolbar,
.snapshot-panel,
.table-panel {
  padding: 12px;
  background: var(--app-surface);
  border: 1px solid var(--app-divider);
  border-radius: 6px;
}

.page__toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.database-selector {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.database-selector__label,
.snapshot-line,
.muted-text {
  color: var(--app-text-secondary);
  font-size: 13px;
}

.database-selector__select {
  width: 220px;
}

.snapshot-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.snapshot-alert {
  margin-bottom: 10px;
}

.online-tag {
  flex: 0 0 auto;
}

.pagination-line {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.action-dialog__form {
  margin-top: 14px;
}
</style>
