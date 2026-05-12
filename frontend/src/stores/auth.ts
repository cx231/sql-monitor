import { defineStore } from 'pinia';

import { apiClient, clearAccessToken, getAccessToken, setAccessToken } from '@/api/client';

const AUTH_STATE_STORAGE_KEY = 'sqlmon.auth_state';

interface LoginPayload {
  username: string;
  password: string;
  captcha_token: string;
  captcha_code: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
  display_name: string | null;
  role: string;
}

export interface CaptchaResponse {
  captcha_token: string;
  image_data_url: string;
  expires_in_seconds: number;
}

interface AuthUser {
  id: string;
  username: string;
  displayName: string | null;
  role: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  loginAt: string | null;
  loading: boolean;
}

interface StoredAuthState {
  user: AuthUser | null;
  loginAt: string | null;
}

function readStoredAuthState(): StoredAuthState {
  try {
    const rawValue = localStorage.getItem(AUTH_STATE_STORAGE_KEY);
    if (!rawValue) {
      return { user: null, loginAt: null };
    }
    const parsed = JSON.parse(rawValue) as StoredAuthState;
    return {
      user: parsed.user ?? null,
      loginAt: parsed.loginAt ?? null,
    };
  } catch {
    return { user: null, loginAt: null };
  }
}

function writeStoredAuthState(state: StoredAuthState): void {
  localStorage.setItem(AUTH_STATE_STORAGE_KEY, JSON.stringify(state));
}

function clearStoredAuthState(): void {
  localStorage.removeItem(AUTH_STATE_STORAGE_KEY);
}

const storedAuthState = readStoredAuthState();

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: getAccessToken(),
    user: storedAuthState.user,
    loginAt: storedAuthState.loginAt,
    loading: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
  },
  actions: {
    async fetchCaptcha() {
      const { data } = await apiClient.get<CaptchaResponse>('/auth/captcha');
      return data;
    },
    async login(payload: LoginPayload) {
      this.loading = true;

      try {
        const { data } = await apiClient.post<LoginResponse>('/auth/login', payload);

        setAccessToken(data.access_token);
        const user = {
          id: data.user_id,
          username: data.username,
          displayName: data.display_name,
          role: data.role,
        };
        this.token = data.access_token;
        this.user = user;
        this.loginAt = new Date().toISOString();
        writeStoredAuthState({ user, loginAt: this.loginAt });

        return this.user;
      } finally {
        this.loading = false;
      }
    },
    logout() {
      clearAccessToken();
      clearStoredAuthState();
      this.token = null;
      this.user = null;
      this.loginAt = null;
    },
  },
});
