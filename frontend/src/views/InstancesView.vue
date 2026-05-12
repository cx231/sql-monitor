<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <div class="page__actions">
        <div class="status-test-control">
          <el-switch v-model="autoTestEnabled" active-text="自动测试" inactive-text="暂停" />
          <el-select v-model="autoTestIntervalSeconds" class="status-test-control__interval" :disabled="!autoTestEnabled">
            <el-option :value="5" label="5 秒" />
            <el-option :value="10" label="10 秒" />
            <el-option :value="30" label="30 秒" />
            <el-option :value="60" label="60 秒" />
            <el-option :value="120" label="120 秒" />
            <el-option :value="300" label="300 秒" />
          </el-select>
          <el-button :loading="testingAllInstances" @click="testAllInstances">测试状态</el-button>
        </div>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增实例</el-button>
        <el-button :icon="Refresh" @click="fetchInstances">刷新</el-button>
      </div>
    </div>

    <DataState :loading="store.loading" :error="error" :empty="!store.items.length" empty-text="暂无实例配置">
      <div class="table-panel">
        <vxe-table :data="store.items" size="small" border height="620">
          <vxe-column field="name" title="实例名" min-width="160" />
          <vxe-column field="environment" title="环境" width="90" />
          <vxe-column field="host" title="主机" min-width="160" />
          <vxe-column field="port" title="端口" width="80" />
          <vxe-column field="database_name" title="数据库" width="130" />
          <vxe-column field="status" title="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag>
            </template>
          </vxe-column>
          <vxe-column field="has_collect_dsn" title="采集 DSN" width="100">
            <template #default="{ row }">
              <el-tag :type="row.has_collect_dsn ? 'success' : 'info'" effect="plain">
                {{ row.has_collect_dsn ? '已配置' : '未配置' }}
              </el-tag>
            </template>
          </vxe-column>
          <vxe-column field="has_kill_dsn" title="终止 DSN" width="100">
            <template #default="{ row }">
              <el-tag :type="row.has_kill_dsn ? 'warning' : 'info'" effect="plain">
                {{ row.has_kill_dsn ? '已配置' : '未配置' }}
              </el-tag>
            </template>
          </vxe-column>
          <vxe-column field="collect_interval_seconds" title="采集间隔" width="100">
            <template #default="{ row }">{{ row.collect_interval_seconds }} 秒</template>
          </vxe-column>
          <vxe-column field="retention_days" title="保留天数" width="100">
            <template #default="{ row }">{{ row.retention_days }} 天</template>
          </vxe-column>
          <vxe-column field="business_owner" title="业务负责人" width="130" />
          <vxe-column field="dba_owner" title="DBA" width="130" />
          <vxe-column field="sqlserver_version" title="SQL Server 版本" min-width="150" />
          <vxe-column field="updated_at" title="更新时间" width="170" :formatter="dateFormatter" />
          <vxe-column title="操作" width="150" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
                <el-button
                  link
                  type="primary"
                  :loading="testingInstanceId === row.id"
                  @click="testExisting(row)"
                >
                  测试
                </el-button>
                <el-button link type="danger" @click="confirmDelete(row)">删除</el-button>
              </div>
            </template>
          </vxe-column>
        </vxe-table>
      </div>
    </DataState>

    <el-dialog
      v-model="createDialogVisible"
      width="min(760px, calc(100vw - 32px))"
      class="instance-dialog"
      :close-on-click-modal="false"
      @closed="resetCreateDialog"
    >
      <template #header>
        <div class="dialog-header">
          <div>
            <h2>{{ dialogTitle }}</h2>
            <p>{{ dialogDescription }}</p>
          </div>
          <el-tag effect="plain" type="primary">SQL 认证</el-tag>
        </div>
      </template>

      <div class="dialog-body">
        <el-form
          ref="createFormRef"
          class="dialog-form"
          label-position="top"
          :model="createForm"
          :rules="createRules"
        >
          <div class="form-section">
            <div class="section-title">
              <span class="section-index section-index--connection">1</span>
              <span>基础连接</span>
            </div>
            <div class="form-grid">
              <el-form-item label="实例名称" prop="name" class="form-grid__full">
                <el-input v-model.trim="createForm.name" placeholder="例如：生产核心库" />
              </el-form-item>
              <el-form-item label="IP 地址" prop="host">
                <el-input v-model.trim="createForm.host" placeholder="10.0.8.12" />
              </el-form-item>
              <el-form-item label="端口" prop="port">
                <el-input-number
                  v-model="createForm.port"
                  :min="1"
                  :max="65535"
                  :controls="false"
                  class="port-input"
                />
              </el-form-item>
            </div>
          </div>

          <div class="form-section">
            <div class="section-title">
              <span class="section-index section-index--auth">2</span>
              <span>SQL 认证</span>
            </div>
            <div class="form-grid">
              <el-form-item label="用户" prop="username">
                <el-input v-model.trim="createForm.username" placeholder="sqlmon_user" />
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input
                  v-model="createForm.password"
                  :placeholder="dialogMode === 'edit' ? '留空则保留原密码' : '请输入密码'"
                  show-password
                  type="password"
                />
              </el-form-item>
              <el-form-item label="数据库" prop="database_name" class="form-grid__full">
                <el-select
                  v-model="createForm.database_name"
                  class="database-select"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="请选择数据库"
                >
                  <el-option
                    v-for="database in databaseOptions"
                    :key="database"
                    :label="database"
                    :value="database"
                  />
                </el-select>
              </el-form-item>
            </div>
          </div>

          <div class="form-section">
            <div class="section-title">
              <span class="section-index section-index--policy">3</span>
              <span>采集策略</span>
            </div>
            <div class="form-grid">
              <el-form-item label="采集间隔" prop="collect_interval_seconds">
                <el-input-number
                  v-model="createForm.collect_interval_seconds"
                  :min="1"
                  :max="3600"
                  :controls="false"
                  class="port-input"
                />
              </el-form-item>
              <el-form-item label="保留天数" prop="retention_days">
                <el-input-number
                  v-model="createForm.retention_days"
                  :min="1"
                  :max="3650"
                  :controls="false"
                  class="port-input"
                />
              </el-form-item>
            </div>
          </div>

          <div class="form-section">
            <div class="section-title">
              <span class="section-index section-index--owner">4</span>
              <span>责任人</span>
            </div>
            <div class="form-grid">
              <el-form-item label="业务负责人" prop="business_owner">
                <el-input v-model.trim="createForm.business_owner" placeholder="请输入业务负责人账号" />
              </el-form-item>
              <el-form-item label="DBA" prop="dba_owner">
                <el-input v-model.trim="createForm.dba_owner" placeholder="请输入 DBA 账号" />
              </el-form-item>
            </div>
          </div>
        </el-form>

        <aside class="test-panel">
          <div>
            <span class="panel-label">连接检查</span>
            <div class="test-result" :class="testResultClass">
              <strong>{{ testResultTitle }}</strong>
              <span>{{ testResultDescription }}</span>
            </div>
          </div>

          <div class="security-note">
            保存后平台会使用该账号进行采集连接。密码不会在列表或编辑状态中回显。
          </div>
        </aside>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <span>建议先完成连接测试，再保存实例。</span>
          <div class="dialog-footer__actions">
            <el-button :loading="testingNewConnection" @click="testNewConnection">测试连接</el-button>
            <el-button @click="createDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="savingInstance" @click="saveInstance">
              {{ dialogMode === 'edit' ? '保存修改' : '保存' }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { Plus, Refresh } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus';
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';

import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import {
  type InstanceConnectionForm,
  type InstanceConnectionTestResult,
  type InstanceItem,
  useInstancesStore,
} from '@/stores/instances';
import { formatDateTime } from '@/utils/format';

const store = useInstancesStore();
const error = ref('');
const createDialogVisible = ref(false);
const createFormRef = ref<FormInstance>();
const savingInstance = ref(false);
const testingNewConnection = ref(false);
const testingInstanceId = ref<string | null>(null);
const testingAllInstances = ref(false);
const connectionTestResult = ref<InstanceConnectionTestResult | null>(null);
const databaseOptions = ref<string[]>(['master']);
const dialogMode = ref<'create' | 'edit'>('create');
const editingInstance = ref<InstanceItem | null>(null);
const autoTestEnabled = ref(false);
const autoTestIntervalSeconds = ref(30);
let autoTestTimer: number | undefined;
const createForm = reactive<InstanceConnectionForm>({
  name: '',
  host: '',
  port: 1433,
  database_name: 'master',
  username: '',
  password: '',
  collect_interval_seconds: 5,
  retention_days: 7,
  business_owner: '',
  dba_owner: '',
  sqlserver_version: null,
});
const createRules: FormRules<InstanceConnectionForm> = {
  name: [{ required: true, message: '请输入实例名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入 IP 地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'change' }],
  database_name: [{ required: true, message: '请选择数据库', trigger: 'change' }],
  username: [
    {
      validator: (_rule, value: string, callback) => {
        if (dialogMode.value === 'create' && !value) {
          callback(new Error('请输入 SQL 认证用户'));
          return;
        }
        callback();
      },
      trigger: 'blur',
    },
  ],
  password: [
    {
      validator: (_rule, value: string, callback) => {
        if (dialogMode.value === 'create' && !value) {
          callback(new Error('请输入密码'));
          return;
        }
        if (dialogMode.value === 'edit' && createForm.username && !value) {
          callback(new Error('重建连接 DSN 时请输入密码'));
          return;
        }
        if (dialogMode.value === 'edit' && value && !createForm.username) {
          callback(new Error('重建连接 DSN 时请输入 SQL 认证用户'));
          return;
        }
        callback();
      },
      trigger: 'blur',
    },
  ],
  collect_interval_seconds: [{ required: true, message: '请输入采集间隔', trigger: 'change' }],
  retention_days: [{ required: true, message: '请输入保留天数', trigger: 'change' }],
};

const dialogTitle = computed(() =>
  dialogMode.value === 'edit' ? '编辑 SQL Server 实例' : '新增 SQL Server 实例',
);
const dialogDescription = computed(() =>
  dialogMode.value === 'edit'
    ? '调整连接和采集策略；用户密码留空时保留原连接凭据。'
    : '填写连接信息后先测试连接，再保存到实例列表。',
);

const testResultClass = computed(() => {
  if (!connectionTestResult.value) {
    return 'test-result--idle';
  }

  return connectionTestResult.value.success ? 'test-result--success' : 'test-result--error';
});

const testResultTitle = computed(() => {
  if (!connectionTestResult.value) {
    return '等待测试';
  }

  return connectionTestResult.value.success ? '测试通过' : '测试失败';
});

const testResultDescription = computed(() => {
  const result = connectionTestResult.value;
  if (!result) {
    return '填写连接信息后点击“测试连接”。';
  }

  if (!result.success) {
    return result.error_message ?? '无法连接到该 SQL Server 实例。';
  }

  const version = result.sqlserver_version ? `版本：${result.sqlserver_version}` : '版本：未返回';
  const database = result.database_name ? `默认数据库：${result.database_name}` : '默认数据库：未返回';
  return `${version}；${database}`;
});

async function fetchInstances() {
  error.value = '';
  try {
    await store.fetchInstances();
  } catch {
    error.value = '无法加载实例列表';
  }
}

function openCreateDialog() {
  dialogMode.value = 'create';
  editingInstance.value = null;
  resetCreateDialog();
  createDialogVisible.value = true;
}

function openEditDialog(row: InstanceItem) {
  dialogMode.value = 'edit';
  editingInstance.value = row;
  createForm.name = row.name;
  createForm.host = row.host;
  createForm.port = row.port;
  createForm.database_name = row.database_name || 'master';
  createForm.username = '';
  createForm.password = '';
  createForm.collect_interval_seconds = row.collect_interval_seconds;
  createForm.retention_days = row.retention_days;
  createForm.business_owner = row.business_owner || '';
  createForm.dba_owner = row.dba_owner || '';
  createForm.sqlserver_version = row.sqlserver_version;
  databaseOptions.value = normalizeDatabaseOptions([row.database_name || 'master']);
  connectionTestResult.value = null;
  createFormRef.value?.clearValidate();
  createDialogVisible.value = true;
}

function normalizeDatabaseOptions(databases: string[] | null | undefined) {
  const uniqueDatabases = Array.from(
    new Set((databases ?? []).map((database) => database.trim()).filter(Boolean)),
  );
  if (!uniqueDatabases.length) {
    return ['master'];
  }
  if (uniqueDatabases.includes('master')) {
    return ['master', ...uniqueDatabases.filter((database) => database !== 'master')];
  }
  return uniqueDatabases;
}

function applyDatabaseOptions(databases: string[] | null | undefined) {
  const options = normalizeDatabaseOptions(databases);
  const selectedDatabase = createForm.database_name;
  databaseOptions.value = options;

  if (selectedDatabase && options.includes(selectedDatabase)) {
    return;
  }

  createForm.database_name = options.includes('master') ? 'master' : options[0];
}

function resetCreateDialog() {
  createForm.name = '';
  createForm.host = '';
  createForm.port = 1433;
  createForm.database_name = 'master';
  createForm.username = '';
  createForm.password = '';
  createForm.collect_interval_seconds = 5;
  createForm.retention_days = 7;
  createForm.business_owner = '';
  createForm.dba_owner = '';
  createForm.sqlserver_version = null;
  databaseOptions.value = ['master'];
  connectionTestResult.value = null;
  createFormRef.value?.clearValidate();
}

async function validateCreateForm() {
  if (!createFormRef.value) {
    return false;
  }

  return await createFormRef.value.validate().catch(() => false);
}

async function testNewConnection() {
  if (!(await validateCreateForm())) {
    return;
  }

  testingNewConnection.value = true;
  try {
    connectionTestResult.value = await store.testNewConnection({ ...createForm });

    if (connectionTestResult.value.success) {
      createForm.sqlserver_version = connectionTestResult.value.sqlserver_version;
      applyDatabaseOptions(connectionTestResult.value.databases);
      ElMessage.success('连接测试通过');
    } else {
      ElMessage.error(connectionTestResult.value.error_message ?? '连接测试失败');
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : '连接测试失败';
    connectionTestResult.value = {
      success: false,
      sqlserver_version: null,
      database_name: null,
      databases: [],
      error_message: message,
      instance: null,
    };
    ElMessage.error(message);
  } finally {
    testingNewConnection.value = false;
  }
}

async function saveInstance() {
  if (!(await validateCreateForm())) {
    return;
  }

  savingInstance.value = true;
  try {
    const payload = {
      ...createForm,
      sqlserver_version: connectionTestResult.value?.success
        ? connectionTestResult.value.sqlserver_version
        : createForm.sqlserver_version,
    };
    if (dialogMode.value === 'edit' && editingInstance.value) {
      await store.updateInstanceFromForm(editingInstance.value.id, payload);
    } else {
      await store.createInstanceFromForm(payload);
    }
    await store.fetchInstances();
    createDialogVisible.value = false;
    ElMessage.success(dialogMode.value === 'edit' ? '实例已更新' : '实例已新增');
  } catch {
    ElMessage.error(dialogMode.value === 'edit' ? '更新实例失败' : '新增实例失败');
  } finally {
    savingInstance.value = false;
  }
}

async function testExisting(row: InstanceItem) {
  testingInstanceId.value = row.id;
  try {
    const result = await store.testExistingConnection(row.id);
    if (result.success) {
      const version = result.sqlserver_version ? `，版本已更新：${result.sqlserver_version}` : '';
      ElMessage.success(`${row.name} 连接测试通过${version}`);
    } else {
      ElMessage.error(result.error_message ?? `${row.name} 连接测试失败`);
    }
  } catch {
    ElMessage.error(`${row.name} 连接测试失败`);
  } finally {
    testingInstanceId.value = null;
  }
}

async function testAllInstances() {
  if (testingAllInstances.value) {
    return;
  }

  testingAllInstances.value = true;
  try {
    for (const instance of [...store.items]) {
      await store.testExistingConnection(instance.id);
    }
    ElMessage.success('实例状态测试完成');
  } catch {
    ElMessage.error('实例状态测试失败');
  } finally {
    testingAllInstances.value = false;
  }
}

async function confirmDelete(row: InstanceItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除实例“${row.name}”？删除后该实例将不再出现在监控实例列表中。`,
      '删除实例',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    );
    await store.deleteInstance(row.id);
    ElMessage.success('实例已删除');
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error('删除实例失败');
    }
  }
}

function statusText(status: string) {
  const map: Record<string, string> = {
    online: '在线',
    offline: '离线',
    collect_error: '采集异常',
    disabled: '禁用',
  };
  return map[status] ?? status;
}

function statusTag(status: string) {
  if (status === 'online') {
    return 'success';
  }
  if (status === 'collect_error') {
    return 'danger';
  }
  if (status === 'offline') {
    return 'warning';
  }
  return 'info';
}

const dateFormatter = ({ cellValue }: { cellValue: string | null | undefined }) => formatDateTime(cellValue);

function resetAutoTestTimer() {
  if (autoTestTimer) {
    window.clearInterval(autoTestTimer);
    autoTestTimer = undefined;
  }
  if (autoTestEnabled.value) {
    autoTestTimer = window.setInterval(() => {
      void testAllInstances();
    }, autoTestIntervalSeconds.value * 1000);
  }
}

watch([autoTestEnabled, autoTestIntervalSeconds], resetAutoTestTimer, { immediate: true });

onBeforeUnmount(() => {
  if (autoTestTimer) {
    window.clearInterval(autoTestTimer);
  }
});

void fetchInstances();
</script>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}

.page__toolbar,
.table-panel {
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

.page__actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.row-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.status-test-control {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.status-test-control__interval {
  width: 92px;
}

.dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-right: 18px;
}

.dialog-header h2 {
  margin: 0 0 6px;
  color: var(--app-text-primary);
  font-size: 18px;
  line-height: 1.3;
}

.dialog-header p {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 13px;
}

.dialog-body {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(220px, 0.75fr);
  border-top: 1px solid var(--app-divider);
  border-bottom: 1px solid var(--app-divider);
}

.dialog-form {
  display: grid;
  gap: 8px;
  padding: 16px 22px 16px 0;
}

.form-section {
  display: grid;
  gap: 5px;
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--app-text-primary);
  font-size: 14px;
  font-weight: 700;
}

.section-index {
  display: inline-flex;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
}

.section-index--connection {
  background: color-mix(in srgb, var(--app-info) 14%, var(--app-surface));
  color: var(--app-info);
}

.section-index--auth {
  background: color-mix(in srgb, var(--app-warning) 16%, var(--app-surface));
  color: var(--app-warning);
}

.section-index--policy {
  background: color-mix(in srgb, var(--app-success) 14%, var(--app-surface));
  color: var(--app-success);
}

.section-index--owner {
  background: color-mix(in srgb, var(--app-primary) 14%, var(--app-surface));
  color: var(--app-primary);
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px 12px;
}

:deep(.dialog-form .el-form-item) {
  margin-bottom: 0;
}

.form-grid__full {
  grid-column: 1 / -1;
}

.port-input {
  width: 100%;
}

.database-select {
  width: 100%;
}

.test-panel {
  display: grid;
  align-content: start;
  gap: 14px;
  padding: 20px;
  background: var(--app-surface-muted);
  border-left: 1px solid var(--app-divider);
}

.panel-label {
  display: block;
  margin-bottom: 8px;
  color: var(--app-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.test-result,
.security-note {
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
}

.test-result {
  display: grid;
  gap: 6px;
  border: 1px solid var(--app-divider);
  background: var(--app-surface);
  color: var(--app-text-secondary);
}

.test-result--success {
  border-color: color-mix(in srgb, var(--app-success) 36%, var(--app-divider));
  background: color-mix(in srgb, var(--app-success) 12%, var(--app-surface));
  color: var(--app-success);
}

.test-result--error {
  border-color: color-mix(in srgb, var(--app-error) 36%, var(--app-divider));
  background: color-mix(in srgb, var(--app-error) 12%, var(--app-surface));
  color: var(--app-error);
}

.security-note {
  border: 1px solid var(--app-divider);
  background: var(--app-surface);
  color: var(--app-text-secondary);
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dialog-footer span {
  color: var(--app-text-secondary);
  font-size: 12px;
}

.dialog-footer__actions {
  display: inline-flex;
  gap: 8px;
}

:deep(.instance-dialog .el-dialog__body) {
  padding-top: 0;
  padding-bottom: 0;
}

@media (max-width: 860px) {
  .page__toolbar,
  .dialog-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .page__actions,
  .dialog-footer__actions {
    justify-content: flex-end;
  }

  .status-test-control {
    justify-content: flex-end;
  }

  .dialog-body,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .dialog-form {
    padding-right: 0;
  }

  .test-panel {
    border-top: 1px solid var(--app-divider);
    border-left: 0;
  }
}
</style>
