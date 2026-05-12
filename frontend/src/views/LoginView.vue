<template>
  <main class="login-view">
    <div class="login-view__scene" aria-hidden="true">
      <div class="login-view__grid"></div>
      <div class="login-view__node login-view__node--primary"></div>
      <div class="login-view__node login-view__node--secondary"></div>
      <div class="login-view__panel login-view__panel--top"></div>
      <div class="login-view__panel login-view__panel--bottom"></div>
    </div>

    <section class="login-panel">
      <div class="login-panel__header">
        <h1>SQL Server 实时监控</h1>
        <p>请使用监控平台账号登录</p>
      </div>

      <div class="login-panel__form-surface">
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
          <el-form-item label="验证码" prop="captchaCode">
            <div class="captcha-row">
              <el-input
                v-model.trim="form.captchaCode"
                autocomplete="off"
                maxlength="6"
                placeholder="请输入6位验证码"
              />
              <button
                class="captcha-image"
                type="button"
                title="点击刷新验证码"
                :disabled="captchaLoading"
                @click="refreshCaptcha"
              >
                <img v-if="captcha.imageDataUrl" :src="captcha.imageDataUrl" alt="验证码" />
                <span v-else>{{ captchaLoading ? '加载中' : '刷新' }}</span>
              </button>
            </div>
            <el-button class="captcha-refresh" link type="primary" :loading="captchaLoading" @click="refreshCaptcha">
              换一张
            </el-button>
          </el-form-item>
          <el-alert v-if="error" class="login-panel__error" type="error" :title="error" :closable="false" />
          <el-button class="login-panel__button" type="primary" :loading="auth.loading" @click="submit">
            登录
          </el-button>
        </el-form>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();
const formRef = ref<FormInstance>();
const error = ref('');
const form = reactive({
  username: '',
  password: '',
  captchaCode: '',
});
const captcha = reactive({
  token: '',
  imageDataUrl: '',
});
const captchaLoading = ref(false);

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captchaCode: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    {
      pattern: /^\d{6}$/,
      message: '验证码必须为6位数字',
      trigger: 'blur',
    },
  ],
};

async function refreshCaptcha() {
  captchaLoading.value = true;
  try {
    const data = await auth.fetchCaptcha();
    captcha.token = data.captcha_token;
    captcha.imageDataUrl = data.image_data_url;
    form.captchaCode = '';
  } catch {
    error.value = '验证码加载失败，请刷新重试';
  } finally {
    captchaLoading.value = false;
  }
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  if (!captcha.token) {
    error.value = '验证码加载失败，请刷新重试';
    return;
  }

  error.value = '';
  try {
    await auth.login({
      username: form.username,
      password: form.password,
      captcha_token: captcha.token,
      captcha_code: form.captchaCode,
    });
    await router.replace('/dashboard');
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    error.value = detail === '验证码错误或已过期' ? detail : '登录失败，请检查用户名或密码';
    await refreshCaptcha();
  }
}

onMounted(refreshCaptcha);
</script>

<style scoped>
.login-view {
  box-sizing: border-box;
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center end;
  padding: 48px clamp(24px, 8vw, 112px);
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 18%, color-mix(in srgb, var(--app-info) 18%, transparent), transparent 28%),
    radial-gradient(circle at 78% 76%, color-mix(in srgb, var(--app-primary) 16%, transparent), transparent 30%),
    linear-gradient(135deg, var(--app-bg), var(--app-surface-muted));
}

.login-view::before {
  position: absolute;
  inset: 0;
  content: '';
  background:
    linear-gradient(115deg, transparent 0 38%, color-mix(in srgb, var(--app-primary) 10%, transparent) 38% 39%, transparent 39% 100%),
    linear-gradient(145deg, transparent 0 58%, color-mix(in srgb, var(--app-info) 10%, transparent) 58% 59%, transparent 59% 100%);
  opacity: 0.9;
}

.login-view__scene {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.login-view__grid {
  position: absolute;
  inset: -20%;
  background-image:
    linear-gradient(color-mix(in srgb, var(--app-divider) 68%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--app-divider) 68%, transparent) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(90deg, rgb(0 0 0 / 84%), transparent 78%);
  transform: perspective(900px) rotateX(58deg) rotateZ(-8deg) translateY(8%);
  transform-origin: 45% 55%;
  opacity: 0.48;
}

.login-view__node {
  position: absolute;
  width: 260px;
  height: 260px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 30%, transparent);
  border-radius: 50%;
  background:
    radial-gradient(circle, color-mix(in srgb, var(--app-primary) 28%, transparent) 0 2px, transparent 3px),
    radial-gradient(circle, color-mix(in srgb, var(--app-info) 14%, transparent), transparent 62%);
  box-shadow: 0 0 80px color-mix(in srgb, var(--app-primary) 14%, transparent);
}

.login-view__node::before,
.login-view__node::after {
  position: absolute;
  content: '';
  border-radius: 999px;
  background: color-mix(in srgb, var(--app-info) 36%, transparent);
}

.login-view__node::before {
  width: 160px;
  height: 1px;
  top: 70px;
  left: 190px;
  transform: rotate(-18deg);
}

.login-view__node::after {
  width: 1px;
  height: 120px;
  right: 68px;
  bottom: -82px;
  transform: rotate(24deg);
}

.login-view__node--primary {
  left: clamp(24px, 10vw, 150px);
  top: 18%;
}

.login-view__node--secondary {
  left: 30%;
  bottom: 10%;
  width: 180px;
  height: 180px;
  opacity: 0.74;
}

.login-view__panel {
  position: absolute;
  width: 360px;
  height: 176px;
  border: 1px solid color-mix(in srgb, var(--app-divider) 78%, transparent);
  border-radius: 8px;
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--app-primary) 22%, transparent), transparent 46%),
    repeating-linear-gradient(
      180deg,
      color-mix(in srgb, var(--app-text-secondary) 22%, transparent) 0 1px,
      transparent 1px 22px
    ),
    color-mix(in srgb, var(--app-surface) 54%, transparent);
  box-shadow: 0 20px 70px rgb(2 6 23 / 12%);
}

.login-view__panel--top {
  top: 16%;
  right: clamp(500px, 44vw, 760px);
  transform: rotate(-4deg);
}

.login-view__panel--bottom {
  right: clamp(470px, 40vw, 720px);
  bottom: 16%;
  width: 300px;
  height: 132px;
  transform: rotate(5deg);
  opacity: 0.78;
}

.login-panel {
  box-sizing: border-box;
  position: relative;
  z-index: 1;
  width: min(430px, 100%);
  padding: 30px;
  background: color-mix(in srgb, var(--app-surface) 94%, transparent);
  border: 1px solid color-mix(in srgb, var(--app-divider) 86%, transparent);
  border-radius: 8px;
  box-shadow: 0 24px 72px rgb(2 6 23 / 18%), var(--app-shadow);
  backdrop-filter: blur(14px);
}

.login-panel__header {
  margin-bottom: 24px;
  padding-bottom: 2px;
}

.login-panel__header h1 {
  margin: 0 0 8px;
  color: var(--app-text-primary);
  font-size: 22px;
}

.login-panel__header p {
  margin: 0;
  color: var(--app-text-secondary);
}

.login-panel__form-surface {
  box-sizing: border-box;
  padding: 18px;
  background: color-mix(in srgb, var(--app-surface-muted) 74%, var(--app-surface));
  border: 1px solid var(--app-divider);
  border-radius: 8px;
  box-shadow:
    inset 0 1px 0 rgb(255 255 255 / 28%),
    0 12px 30px rgb(2 6 23 / 6%);
}

.login-panel__error {
  margin-bottom: 16px;
}

.login-panel__button {
  width: 100%;
}

.captcha-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 132px;
  gap: 10px;
  width: 100%;
}

.captcha-image {
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  overflow: hidden;
  color: var(--app-text-secondary);
  background: var(--app-surface-muted);
  border: 1px solid var(--app-divider);
  border-radius: 6px;
  cursor: pointer;
}

.captcha-image:disabled {
  cursor: wait;
  opacity: 0.72;
}

.captcha-image img {
  display: block;
  width: 132px;
  height: 44px;
}

.captcha-refresh {
  margin-top: 6px;
  padding: 0;
}

@media (max-width: 760px) {
  .login-view {
    place-items: center;
    padding: 24px;
  }

  .login-view__grid {
    opacity: 0.26;
    transform: none;
    mask-image: linear-gradient(rgb(0 0 0 / 68%), transparent 84%);
  }

  .login-view__panel {
    display: none;
  }

  .login-view__node--primary {
    left: -96px;
    top: 8%;
  }

  .login-view__node--secondary {
    right: -80px;
    left: auto;
    bottom: 4%;
  }

  .login-panel {
    padding: 22px;
  }

  .login-panel__form-surface {
    padding: 16px;
  }
}

@media (max-width: 420px) {
  .captcha-row {
    grid-template-columns: 1fr;
  }

  .captcha-image,
  .captcha-image img {
    width: 100%;
  }
}
</style>
