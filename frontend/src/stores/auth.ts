import { defineStore } from 'pinia';

import { apiClient, clearAccessToken, getAccessToken, setAccessToken } from '@/api/client';

interface LoginPayload {
  username: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
  display_name: string | null;
  role: string;
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
  loading: boolean;
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: getAccessToken(),
    user: null,
    loading: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
  },
  actions: {
    async login(payload: LoginPayload) {
      this.loading = true;

      try {
        const { data } = await apiClient.post<LoginResponse>('/auth/login', payload);

        setAccessToken(data.access_token);
        this.token = data.access_token;
        this.user = {
          id: data.user_id,
          username: data.username,
          displayName: data.display_name,
          role: data.role,
        };

        return this.user;
      } finally {
        this.loading = false;
      }
    },
    logout() {
      clearAccessToken();
      this.token = null;
      this.user = null;
    },
  },
});
