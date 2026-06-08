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
        :disabled="!selectedDatabase || missingLoading"
        :loading="missingLoading"
        @click="refreshMissingIndexes"
      >
        刷新
      </el-button>
    </div>

    <div v-if="selectedDatabase" class="snapshot-panel">
      <div class="snapshot-line">
        快照最后更新时间：{{ snapshotUpdatedAtText }}
        <el-tag class="status-tag" :type="collectionStatusTag" effect="plain">
          {{ collectionStatusText }}
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
      :loading="databasesLoading || (missingLoading && !rows.length)"
      :error="error"
      :empty="!selectedDatabase || !rows.length"
      :empty-text="emptyText"
      loading-text="正在加载缺失索引快照..."
    >
      <div v-loading="missingLoading" class="table-panel" element-loading-text="正在加载缺失索引快照...">
        <vxe-table :data="rows" size="small" border height="620">
          <vxe-column field="schema_name" title="Schema" width="120" />
          <vxe-column field="table_name" title="表名" width="180" show-overflow />
          <vxe-column title="键列" min-width="240" show-overflow>
            <template #default="{ row }">
              {{ formatColumns(keyColumns(row)) }}
            </template>
          </vxe-column>
          <vxe-column title="包含列" min-width="220" show-overflow>
            <template #default="{ row }">
              {{ formatColumns(row.include_columns) }}
            </template>
          </vxe-column>
          <vxe-column field="user_seeks" title="Seeks" width="100" align="right" :formatter="numberFormatter" />
          <vxe-column field="user_scans" title="Scans" width="100" align="right" :formatter="numberFormatter" />
          <vxe-column field="avg_total_user_cost" title="平均成本" width="110" align="right" :formatter="decimalFormatter" />
          <vxe-column field="avg_user_impact" title="影响%" width="100" align="right" :formatter="decimalFormatter" />
          <vxe-column field="recommended_index_name" title="建议索引名" min-width="260" show-overflow />
          <vxe-column title="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                :disabled="!row.create_enabled"
                @click="openCreateDialog(row)"
              >
                新建索引
              </el-button>
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
            :disabled="missingLoading"
            @current-change="handlePageChange"
            @size-change="handlePageSizeChange"
          />
        </div>
      </div>
    </DataState>

    <el-dialog v-model="createVisible" title="新建索引" width="560px" destroy-on-close>
      <template v-if="createTarget">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="该操作会在 SQL Server 中执行 CREATE INDEX，请确认目标库表和索引名。"
        />
        <el-form class="create-dialog__form" label-position="top">
          <el-form-item label="目标">
            <el-input :model-value="targetLabel" disabled />
          </el-form-item>
          <el-form-item label="键列">
            <el-input :model-value="formatColumns(keyColumns(createTarget))" disabled />
          </el-form-item>
          <el-form-item label="包含列">
            <el-input :model-value="formatColumns(createTarget.include_columns)" disabled />
          </el-form-item>
          <el-form-item label="索引名">
            <el-input v-model="indexName" maxlength="128" show-word-limit />
          </el-form-item>
        </el-form>
      </template>

      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="createLoading"
          :disabled="!indexName.trim()"
          @click="createIndex"
        >
          确认创建
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
  IndexCreateResponse,
  IndexAuditOut,
  IndexDatabaseListOut,
  MissingIndexItem,
  MissingIndexListOut,
} from '@/api/types';
import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import { useInstancesStore } from '@/stores/instances';
import { formatNumber } from '@/utils/format';
import { formatSnapshotDateTime } from '@/utils/format';

const instancesStore = useInstancesStore();
const databases = ref<string[]>([]);
const selectedDatabase = ref<string | null>(null);
const rows = ref<MissingIndexItem[]>([]);
const checkedAt = ref<string | null>(null);
const collectionStatus = ref('unknown');
const collectionError = ref<string | null>(null);
const stale = ref(true);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const databasesLoading = ref(false);
const missingLoading = ref(false);
const createLoading = ref(false);
const error = ref('');
const createVisible = ref(false);
const createTarget = ref<MissingIndexItem | null>(null);
const indexName = ref('');
let missingRequestSeq = 0;
let missingAbortController: AbortController | null = null;
const AUDIT_POLL_INTERVAL_MS = 2000;
const AUDIT_POLL_ATTEMPTS = 10;

const currentInstanceId = computed(() => instancesStore.currentInstance?.id ?? null);
const emptyText = computed(() => {
  if (!selectedDatabase.value) {
    return '请选择用户库';
  }
  return '当前用户库暂无缺失索引建议';
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
    return '等待 collector 采集缺失索引数据';
  }
  if (stale.value) {
    return '本地缺失索引快照可能已过期，请确认 collector 运行状态';
  }
  return '';
});
const collectionNoticeType = computed(() => (collectionStatus.value === 'failed' ? 'error' : 'warning'));
const snapshotUpdatedAtText = computed(() => formatSnapshotDateTime(checkedAt.value));
const targetLabel = computed(() => {
  const target = createTarget.value;
  if (!target) {
    return '-';
  }
  return `${target.database_name}.${target.schema_name}.${target.table_name}`;
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

async function fetchMissingIndexes() {
  const instanceId = currentInstanceId.value;
  const databaseName = selectedDatabase.value;
  if (!instanceId || !databaseName) {
    return;
  }

  missingLoading.value = true;
  error.value = '';
  const requestSeq = ++missingRequestSeq;
  missingAbortController?.abort();
  missingAbortController = new AbortController();
  try {
    const { data } = await apiClient.get<MissingIndexListOut>('/indexes/missing', {
      params: {
        instance_id: instanceId,
        database_name: databaseName,
        page: page.value,
        page_size: pageSize.value,
      },
      signal: missingAbortController.signal,
    });
    if (requestSeq !== missingRequestSeq) {
      return;
    }
    rows.value = data.items.slice(0, pageSize.value);
    checkedAt.value = data.checked_at;
    collectionStatus.value = data.collection_status;
    collectionError.value = data.collection_error;
    stale.value = data.stale;
    page.value = data.page;
    pageSize.value = data.page_size;
    total.value = data.total;
  } catch (fetchError) {
    if (axios.isCancel(fetchError)) {
      return;
    }
    if (requestSeq !== missingRequestSeq) {
      return;
    }
    rows.value = [];
    checkedAt.value = null;
    collectionStatus.value = 'failed';
    collectionError.value = requestMessage(fetchError, '无法加载缺失索引本地快照');
    stale.value = true;
    total.value = 0;
    error.value = collectionError.value;
  } finally {
    if (requestSeq === missingRequestSeq) {
      missingLoading.value = false;
      missingAbortController = null;
    }
  }
}

async function refreshMissingIndexes() {
  page.value = 1;
  await fetchMissingIndexes();
}

async function handlePageSizeChange() {
  page.value = 1;
  await fetchMissingIndexes();
}

async function handlePageChange() {
  await fetchMissingIndexes();
}

function openCreateDialog(row: MissingIndexItem) {
  createTarget.value = row;
  indexName.value = row.recommended_index_name;
  createVisible.value = true;
}

async function createIndex() {
  const instanceId = currentInstanceId.value;
  const target = createTarget.value;
  const name = indexName.value.trim();
  if (!instanceId || !target || !name) {
    return;
  }

  createLoading.value = true;
  try {
    const { data } = await apiClient.post<IndexCreateResponse>(
      '/indexes',
      {
        instance_id: instanceId,
        database_name: target.database_name,
        schema_name: target.schema_name,
        table_name: target.table_name,
        key_columns: keyColumns(target),
        include_columns: target.include_columns,
        index_name: name,
      },
      { timeout: INDEX_OPERATION_TIMEOUT_MS },
    );
    if (data.result === 'success') {
      ElMessage.success('索引创建成功');
      createVisible.value = false;
      await refreshMissingIndexes();
      return;
    }
    if (data.result === 'running') {
      ElMessage.success('索引创建已提交后台执行，请稍后刷新确认结果');
      createVisible.value = false;
      void pollIndexAudit(data.audit_id, 'create');
      return;
    }
    ElMessage.warning(data.error_message || '索引创建未成功');
  } catch (createError) {
    const message = requestMessage(createError, '索引创建失败');
    if (message === 'INDEX_NAME_CONFLICT') {
      ElMessage.error('索引名已存在，请修改索引名');
    } else if (message === 'OPERATION_DSN_NOT_CONFIGURED') {
      ElMessage.error('未配置可执行数据库连接，无法创建索引');
    } else if (message === 'INDEX_CREATE_TIMEOUT') {
      ElMessage.error('索引创建执行超时，请检查目标表大小、锁等待或稍后重试');
    } else if (message === 'CLIENT_TIMEOUT') {
      ElMessage.error('前端等待索引创建超时，后台可能仍在执行，请稍后刷新确认结果');
    } else {
      ElMessage.error(message);
    }
  } finally {
    createLoading.value = false;
  }
}

async function pollIndexAudit(auditId: string, action: 'create') {
  for (let attempt = 0; attempt < AUDIT_POLL_ATTEMPTS; attempt += 1) {
    await delay(AUDIT_POLL_INTERVAL_MS);
    try {
      const { data } = await apiClient.get<IndexAuditOut>(`/indexes/audits/${auditId}`);
      if (data.result === 'running') {
        continue;
      }
      if (data.result === 'success') {
        ElMessage.success(action === 'create' ? '索引创建完成' : '索引操作完成');
        await refreshMissingIndexes();
        return;
      }
      ElMessage.error(indexAuditErrorText(data.error_message, '索引创建失败'));
      return;
    } catch {
      return;
    }
  }
  ElMessage.info('索引创建仍在后台执行，请稍后刷新确认结果');
}

function delay(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function indexAuditErrorText(message: string | null, fallback: string) {
  if (message === 'INDEX_CREATE_TIMEOUT') {
    return '索引创建执行超时，请检查目标表大小、锁等待或稍后重试';
  }
  if (message === 'INDEX_CREATE_FAILED') {
    return fallback;
  }
  return message || fallback;
}

function keyColumns(row: MissingIndexItem) {
  return [...row.equality_columns, ...row.inequality_columns];
}

function formatColumns(columns: string[]) {
  return columns.length ? columns.join(', ') : '-';
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
const decimalFormatter = ({ cellValue }: { cellValue: number | null | undefined }) => {
  if (cellValue === null || cellValue === undefined) {
    return '-';
  }
  return cellValue.toFixed(1);
};

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
  page.value = 1;
  total.value = 0;
  void fetchMissingIndexes();
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
.snapshot-line {
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

.status-tag {
  flex: 0 0 auto;
}

.pagination-line {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.create-dialog__form {
  margin-top: 14px;
}
</style>
