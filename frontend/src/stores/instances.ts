import { defineStore } from 'pinia';

import { apiClient } from '@/api/client';

export interface InstanceItem {
  id: string;
  name: string;
  host: string;
  port: number;
  database_name: string | null;
  environment: string;
  has_collect_dsn: boolean;
  has_kill_dsn: boolean;
  status: string;
  collect_interval_seconds: number;
  retention_days: number;
  business_owner: string | null;
  dba_owner: string | null;
  sqlserver_version: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface InstancesState {
  items: InstanceItem[];
  currentInstanceId: string | null;
  loading: boolean;
}

export const useInstancesStore = defineStore('instances', {
  state: (): InstancesState => ({
    items: [],
    currentInstanceId: null,
    loading: false,
  }),
  getters: {
    currentInstance: (state) =>
      state.items.find((item) => item.id === state.currentInstanceId) ?? state.items[0] ?? null,
  },
  actions: {
    async fetchInstances() {
      this.loading = true;

      try {
        const { data } = await apiClient.get<InstanceItem[]>('/instances');
        this.items = data;

        if (!this.currentInstanceId && data.length > 0) {
          this.currentInstanceId = data[0].id;
        }
      } finally {
        this.loading = false;
      }
    },
    setCurrentInstance(instanceId: string | null) {
      this.currentInstanceId = instanceId;
    },
  },
});
