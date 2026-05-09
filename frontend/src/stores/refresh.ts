import { defineStore } from 'pinia';

interface RefreshState {
  enabled: boolean;
  intervalSeconds: number;
  tick: number;
}

export const useRefreshStore = defineStore('refresh', {
  state: (): RefreshState => ({
    enabled: true,
    intervalSeconds: 5,
    tick: 0,
  }),
  actions: {
    setEnabled(enabled: boolean) {
      this.enabled = enabled;
    },
    setIntervalSeconds(seconds: number) {
      this.intervalSeconds = Math.max(1, seconds);
    },
    requestRefresh() {
      this.tick += 1;
    },
  },
});
