<template>
  <main class="login-view">
    <section class="login-panel">
      <div class="login-panel__header">
        <h1>SQL Server 实时监控</h1>
        <p>请使用监控平台账号登录</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            show-password
            placeholder="请输入密码"
          />
        </el-form-item>
        <el-alert v-if="error" class="login-panel__error" type="error" :title="error" :closable="false" />
        <el-button class="login-panel__button" type="primary" :loading="auth.loading" @click="submit">
          登录
        </el-button>
      </el-form>
    </section>
  </main>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();
const formRef = ref<FormInstance>();
const error = ref('');
const form = reactive({
  username: '',
  password: '',
});

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
};

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }

  error.value = '';
  try {
    await auth.login(form);
    await router.replace('/dashboard');
  } catch {
    error.value = '登录失败，请检查用户名或密码';
  }
}
</script>

<style scoped>
.login-view {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: #eef2f6;
}

.login-panel {
  width: min(420px, 100%);
  padding: 28px;
  background: #ffffff;
  border: 1px solid #dfe5ec;
  border-radius: 8px;
  box-shadow: 0 14px 40px rgb(15 23 42 / 8%);
}

.login-panel__header {
  margin-bottom: 24px;
}

.login-panel__header h1 {
  margin: 0 0 8px;
  color: #1f2937;
  font-size: 22px;
}

.login-panel__header p {
  margin: 0;
  color: #606266;
}

.login-panel__error {
  margin-bottom: 16px;
}

.login-panel__button {
  width: 100%;
}
</style>
