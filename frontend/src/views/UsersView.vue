<template>
  <section class="page">
    <div class="page__toolbar">
      <div>
        <h2>用户管理</h2>
        <p>维护平台登录账号、角色权限和账号状态。</p>
      </div>
      <div class="page__actions">
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增用户</el-button>
        <el-button :icon="Refresh" @click="fetchUsers">刷新</el-button>
      </div>
    </div>

    <DataState :loading="loading" :error="error" :empty="!users.length" empty-text="暂无用户">
      <div class="table-panel">
        <vxe-table :data="users" size="small" border height="620">
          <vxe-column field="username" title="用户名" min-width="150" />
          <vxe-column field="display_name" title="显示名称" min-width="150">
            <template #default="{ row }">{{ row.display_name || '-' }}</template>
          </vxe-column>
          <vxe-column field="role" title="角色" width="130">
            <template #default="{ row }">
              <el-tag effect="plain" :type="roleTag(row.role)">{{ roleLabel(row.role) }}</el-tag>
            </template>
          </vxe-column>
          <vxe-column field="status" title="状态" width="110">
            <template #default="{ row }">
              <el-tag effect="plain" :type="row.status === 'active' ? 'success' : 'info'">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </vxe-column>
          <vxe-column title="权限项" min-width="360">
            <template #default="{ row }">{{ rolePermissionText(row.role) }}</template>
          </vxe-column>
          <vxe-column field="created_at" title="创建时间" width="170" :formatter="dateFormatter" />
          <vxe-column field="updated_at" title="更新时间" width="170" :formatter="dateFormatter" />
          <vxe-column title="操作" width="190" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
                <el-button link type="primary" @click="openResetDialog(row)">重置密码</el-button>
                <el-button
                  link
                  type="danger"
                  :disabled="row.id === auth.user?.id || row.status === 'disabled'"
                  @click="confirmDisable(row)"
                >
                  禁用
                </el-button>
              </div>
            </template>
          </vxe-column>
        </vxe-table>
      </div>
    </DataState>

    <el-dialog
      v-model="userDialogVisible"
      width="min(620px, calc(100vw - 32px))"
      class="user-dialog"
      :close-on-click-modal="false"
      @closed="resetUserDialog"
    >
      <template #header>
        <div class="dialog-header">
          <div>
            <h2>{{ dialogMode === 'edit' ? '编辑用户' : '新增用户' }}</h2>
            <p>角色决定用户可访问的监控数据和管理能力。</p>
          </div>
          <el-tag effect="plain" type="primary">本地账号</el-tag>
        </div>
      </template>

      <el-form ref="userFormRef" class="dialog-form" label-position="top" :model="userForm" :rules="userRules">
        <div class="form-grid">
          <el-form-item label="用户名" prop="username">
            <el-input v-model.trim="userForm.username" :disabled="dialogMode === 'edit'" placeholder="alice" />
          </el-form-item>
          <el-form-item label="显示名称" prop="display_name">
            <el-input v-model.trim="userForm.display_name" placeholder="例如：Alice" />
          </el-form-item>
          <el-form-item v-if="dialogMode === 'create'" label="初始密码" prop="password">
            <el-input v-model="userForm.password" type="password" show-password placeholder="至少 8 位" />
          </el-form-item>
          <el-form-item label="角色" prop="role">
            <el-select v-model="userForm.role" class="full-width">
              <el-option
                v-for="option in roleOptions"
                :key="option.value"
                :label="`${option.label} - ${option.description}`"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="dialogMode === 'edit'" label="状态" prop="status">
            <el-select v-model="userForm.status" class="full-width" :disabled="editingUser?.id === auth.user?.id">
              <el-option label="启用" value="active" />
              <el-option label="禁用" value="disabled" />
            </el-select>
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingUser" @click="saveUser">
          {{ dialogMode === 'edit' ? '保存修改' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="resetDialogVisible"
      width="min(520px, calc(100vw - 32px))"
      title="重置密码"
      :close-on-click-modal="false"
      @closed="resetPasswordForm"
    >
      <el-form ref="passwordFormRef" label-position="top" :model="passwordForm" :rules="passwordRules">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="passwordForm.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resettingPassword" @click="resetPassword">保存密码</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { Plus, Refresh } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus';
import { reactive, ref } from 'vue';

import { apiClient } from '@/api/client';
import type {
  UserCreatePayload,
  UserItem,
  UserPasswordResetPayload,
  UserRole,
  UserStatus,
  UserUpdatePayload,
} from '@/api/types';
import DataState from '@/components/DataState.vue';
import { useAuthStore } from '@/stores/auth';
import { formatDateTime } from '@/utils/format';

interface UserForm {
  username: string;
  password: string;
  display_name: string;
  role: UserRole;
  status: UserStatus;
}

interface PasswordForm {
  password: string;
}

const roleOptions: Array<{ value: UserRole; label: string; description: string }> = [
  { value: 'viewer', label: 'Viewer', description: '基础指标只读' },
  { value: 'developer', label: 'Developer', description: 'Session、SQL、历史和完整 SQL' },
  { value: 'dba', label: 'DBA', description: '全部监控、Kill 和审计' },
  { value: 'admin', label: 'Admin', description: '实例、用户和系统配置' },
];

const auth = useAuthStore();
const users = ref<UserItem[]>([]);
const loading = ref(false);
const error = ref('');
const userDialogVisible = ref(false);
const resetDialogVisible = ref(false);
const savingUser = ref(false);
const resettingPassword = ref(false);
const dialogMode = ref<'create' | 'edit'>('create');
const editingUser = ref<UserItem | null>(null);
const passwordUser = ref<UserItem | null>(null);
const userFormRef = ref<FormInstance>();
const passwordFormRef = ref<FormInstance>();
const userForm = reactive<UserForm>({
  username: '',
  password: '',
  display_name: '',
  role: 'viewer',
  status: 'active',
});
const passwordForm = reactive<PasswordForm>({
  password: '',
});
const userRules: FormRules<UserForm> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    {
      validator: (_rule, value: string, callback) => {
        if (dialogMode.value === 'create' && value.length < 8) {
          callback(new Error('密码至少 8 位'));
          return;
        }
        callback();
      },
      trigger: 'blur',
    },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
};
const passwordRules: FormRules<PasswordForm> = {
  password: [{ min: 8, required: true, message: '密码至少 8 位', trigger: 'blur' }],
};

async function fetchUsers() {
  loading.value = true;
  error.value = '';
  try {
    const { data } = await apiClient.get<UserItem[]>('/users');
    users.value = data;
  } catch {
    error.value = '无法加载用户列表';
  } finally {
    loading.value = false;
  }
}

function openCreateDialog() {
  dialogMode.value = 'create';
  editingUser.value = null;
  resetUserDialog();
  userDialogVisible.value = true;
}

function openEditDialog(row: UserItem) {
  dialogMode.value = 'edit';
  editingUser.value = row;
  userForm.username = row.username;
  userForm.password = '';
  userForm.display_name = row.display_name || '';
  userForm.role = row.role;
  userForm.status = row.status;
  userDialogVisible.value = true;
}

function openResetDialog(row: UserItem) {
  passwordUser.value = row;
  resetPasswordForm();
  resetDialogVisible.value = true;
}

function resetUserDialog() {
  userForm.username = '';
  userForm.password = '';
  userForm.display_name = '';
  userForm.role = 'viewer';
  userForm.status = 'active';
  userFormRef.value?.clearValidate();
}

function resetPasswordForm() {
  passwordForm.password = '';
  passwordFormRef.value?.clearValidate();
}

async function validateUserForm() {
  if (!userFormRef.value) {
    return false;
  }
  return await userFormRef.value.validate().catch(() => false);
}

async function validatePasswordForm() {
  if (!passwordFormRef.value) {
    return false;
  }
  return await passwordFormRef.value.validate().catch(() => false);
}

async function saveUser() {
  if (!(await validateUserForm())) {
    return;
  }

  savingUser.value = true;
  try {
    if (dialogMode.value === 'edit' && editingUser.value) {
      const payload: UserUpdatePayload = {
        display_name: userForm.display_name || null,
        role: userForm.role,
        status: userForm.status,
      };
      await apiClient.put<UserItem>(`/users/${editingUser.value.id}`, payload);
    } else {
      const payload: UserCreatePayload = {
        username: userForm.username,
        password: userForm.password,
        display_name: userForm.display_name || null,
        role: userForm.role,
      };
      await apiClient.post<UserItem>('/users', payload);
    }
    await fetchUsers();
    userDialogVisible.value = false;
    ElMessage.success(dialogMode.value === 'edit' ? '用户已更新' : '用户已新增');
  } catch {
    ElMessage.error(dialogMode.value === 'edit' ? '更新用户失败' : '新增用户失败');
  } finally {
    savingUser.value = false;
  }
}

async function confirmDisable(row: UserItem) {
  try {
    await ElMessageBox.confirm(
      `确认禁用用户“${row.username}”？禁用后该用户将无法登录平台。`,
      '禁用用户',
      {
        confirmButtonText: '禁用',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    );
    await apiClient.post<UserItem>(`/users/${row.id}/disable`);
    await fetchUsers();
    ElMessage.success('用户已禁用');
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error('禁用用户失败');
    }
  }
}

async function resetPassword() {
  if (!passwordUser.value || !(await validatePasswordForm())) {
    return;
  }

  resettingPassword.value = true;
  try {
    const payload: UserPasswordResetPayload = { password: passwordForm.password };
    await apiClient.post<UserItem>(`/users/${passwordUser.value.id}/reset-password`, payload);
    resetDialogVisible.value = false;
    ElMessage.success('密码已重置');
  } catch {
    ElMessage.error('重置密码失败');
  } finally {
    resettingPassword.value = false;
  }
}

function roleLabel(role: UserRole) {
  return roleOptions.find((option) => option.value === role)?.label ?? role;
}

function rolePermissionText(role: UserRole) {
  return roleOptions.find((option) => option.value === role)?.description ?? '-';
}

function roleTag(role: UserRole) {
  const map: Record<UserRole, 'info' | 'primary' | 'warning' | 'danger'> = {
    viewer: 'info',
    developer: 'primary',
    dba: 'warning',
    admin: 'danger',
  };
  return map[role];
}

function statusLabel(status: UserStatus) {
  return status === 'active' ? '启用' : '禁用';
}

const dateFormatter = ({ cellValue }: { cellValue: string | null | undefined }) => formatDateTime(cellValue);

void fetchUsers();
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

.page__toolbar h2 {
  margin: 0;
  color: var(--app-text-primary);
  font-size: 18px;
}

.page__toolbar p {
  margin: 4px 0 0;
  color: var(--app-text-secondary);
  font-size: 13px;
}

.page__actions,
.row-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.dialog-header h2 {
  margin: 0;
  color: var(--app-text-primary);
  font-size: 18px;
}

.dialog-header p {
  margin: 6px 0 0;
  color: var(--app-text-secondary);
  font-size: 13px;
}

.dialog-form {
  padding-top: 4px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.full-width {
  width: 100%;
}

@media (max-width: 760px) {
  .page__toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
