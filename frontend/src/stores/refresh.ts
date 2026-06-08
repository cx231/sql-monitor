import { defineStore } from 'pinia';

const REFRESH_INTERVAL_STORAGE_KEY = 'sqlmon.refresh_interval_seconds';
const REFRESH_INTERVAL_OPTIONS = [5, 10, 30, 60, 120, 300] as const;
const DEFAULT_REFRESH_INTERVAL_SECONDS = 5;

interface RefreshState {
  enabled: boolean;
  intervalSeconds: number;
  tick: number;
}

function normalizeRefreshIntervalSeconds(value: number): number {
  return REFRESH_INTERVAL_OPTIONS.includes(value as (typeof REFRESH_INTERVAL_OPTIONS)[number])
    ? value
    : DEFAULT_REFRESH_INTERVAL_SECONDS;
}

function readStoredIntervalSeconds(): number {
  const storedValue = Number(localStorage.getItem(REFRESH_INTERVAL_STORAGE_KEY));
  return normalizeRefreshIntervalSeconds(storedValue);
}

function writeStoredIntervalSeconds(seconds: number): void {
  localStorage.setItem(REFRESH_INTERVAL_STORAGE_KEY, String(seconds));
}

export const useRefreshStore = defineStore('refresh', {
  state: (): RefreshState => ({
    enabled: true,
    intervalSeconds: readStoredIntervalSeconds(),
    tick: 0,
  }),
  actions: {
    setEnabled(enabled: boolean) {
      this.enabled = enabled;
    },
    setIntervalSeconds(seconds: number) {
      this.intervalSeconds = normalizeRefreshIntervalSeconds(seconds);
      writeStoredIntervalSeconds(this.intervalSeconds);
    },
    requestRefresh() {
      this.tick += 1;
    },
  },
});

export { REFRESH_INTERVAL_OPTIONS, REFRESH_INTERVAL_STORAGE_KEY };
