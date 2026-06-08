import axios from 'axios';

const TOKEN_STORAGE_KEY = 'sqlmon.access_token';
export const INDEX_OPERATION_TIMEOUT_MS = 30 * 60 * 1000;

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeout: 15000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearAccessToken();

      const requestUrl = error.config?.url ?? '';
      const isLoginRequest = requestUrl.includes('/auth/login');
      const isLoginPage = window.location.pathname === '/login';
      if (!isLoginRequest && !isLoginPage) {
        window.location.assign('/login');
      }
    }

    return Promise.reject(error);
  },
);

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export { TOKEN_STORAGE_KEY };
