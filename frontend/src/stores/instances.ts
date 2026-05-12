import { defineStore } from 'pinia';
import axios from 'axios';

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

export interface InstanceConnectionForm {
  name: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  collect_interval_seconds: number;
  retention_days: number;
  business_owner: string;
  dba_owner: string;
  sqlserver_version?: string | null;
}

export interface InstanceConnectionTestResult {
  success: boolean;
  sqlserver_version: string | null;
  database_name: string | null;
  databases: string[];
  error_message: string | null;
  instance: InstanceItem | null;
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
    async createInstanceFromForm(form: InstanceConnectionForm) {
      const { data } = await apiClient.post<InstanceItem>('/instances', {
        name: form.name,
        host: form.host,
        port: form.port,
        database_name: form.database_name || 'master',
        username: form.username,
        password: form.password,
        collect_interval_seconds: form.collect_interval_seconds,
        retention_days: form.retention_days,
        business_owner: form.business_owner || null,
        dba_owner: form.dba_owner || null,
        sqlserver_version: form.sqlserver_version,
        status: 'offline',
      });
      this.items = [data, ...this.items.filter((item) => item.id !== data.id)];

      if (!this.currentInstanceId) {
        this.currentInstanceId = data.id;
      }

      return data;
    },
    async updateInstanceFromForm(instanceId: string, form: InstanceConnectionForm) {
      const payload: Record<string, unknown> = {
        name: form.name,
        host: form.host,
        port: form.port,
        database_name: form.database_name || 'master',
        collect_interval_seconds: form.collect_interval_seconds,
        retention_days: form.retention_days,
        business_owner: form.business_owner || null,
        dba_owner: form.dba_owner || null,
      };

      if (form.username && form.password) {
        payload.username = form.username;
        payload.password = form.password;
      }
      if (form.sqlserver_version) {
        payload.sqlserver_version = form.sqlserver_version;
      }

      const { data } = await apiClient.put<InstanceItem>(`/instances/${instanceId}`, payload);
      this.items = this.items.map((item) => (item.id === data.id ? data : item));
      return data;
    },
    async testNewConnection(form: InstanceConnectionForm) {
      try {
        const { data } = await apiClient.post<InstanceConnectionTestResult>('/instances/test-connection', {
          host: form.host,
          port: form.port,
          database_name: form.database_name || 'master',
          username: form.username,
          password: form.password,
        });
        return data;
      } catch (error) {
        if (axios.isAxiosError(error)) {
          const status = error.response?.status;
          const message = typeof error.response?.data?.detail === 'string'
            ? error.response.data.detail
            : null;
          if (status === 401 || status === 403) {
            throw new Error(message || '当前登录状态无权测试实例连接，请重新登录');
          }
          if (message) {
            throw new Error(message);
          }
        }
        throw new Error('连接测试失败');
      }
    },
    async testExistingConnection(instanceId: string) {
      const { data } = await apiClient.post<InstanceConnectionTestResult>(
        `/instances/${instanceId}/test-connection`,
      );
      if (data.instance) {
        this.items = this.items.map((item) => (item.id === data.instance?.id ? data.instance : item));
      }
      return data;
    },
    async deleteInstance(instanceId: string) {
      await apiClient.delete(`/instances/${instanceId}`);
      this.items = this.items.filter((item) => item.id !== instanceId);

      if (this.currentInstanceId === instanceId) {
        this.currentInstanceId = this.items[0]?.id ?? null;
      }
    },
  },
});
