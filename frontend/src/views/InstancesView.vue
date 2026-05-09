<template>
  <section class="page">
    <div class="page__toolbar">
      <InstanceSelector />
      <el-button :icon="Refresh" @click="fetchInstances">刷新</el-button>
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
          <vxe-column field="has_kill_dsn" title="Kill DSN" width="100">
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
        </vxe-table>
      </div>
    </DataState>
  </section>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue';
import { ref } from 'vue';

import DataState from '@/components/DataState.vue';
import InstanceSelector from '@/components/InstanceSelector.vue';
import { useInstancesStore } from '@/stores/instances';
import { formatDateTime } from '@/utils/format';

const store = useInstancesStore();
const error = ref('');

async function fetchInstances() {
  error.value = '';
  try {
    await store.fetchInstances();
  } catch {
    error.value = '无法加载实例列表';
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
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
