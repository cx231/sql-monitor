import type { InstanceItem } from '@/stores/instances';
import { formatDateTime } from '@/utils/format';

export const STALE_COLLECT_DELAY_SECONDS = 15;

export function isRealtimeStale(collectDelaySeconds: number | null | undefined): boolean {
  return (collectDelaySeconds ?? 0) > STALE_COLLECT_DELAY_SECONDS;
}

export function realtimeStaleText(instance: InstanceItem | null | undefined): string {
  if (instance?.collect_status === 'failed' || instance?.status === 'collect_error') {
    const lastSuccess = formatDateTime(instance.last_success_at);
    const lastFailure = formatDateTime(instance.last_failure_at);
    const error = instance.collect_error_message || '采集失败';
    return `Collector 采集异常：${error}。最近成功：${lastSuccess}；最近失败：${lastFailure}。`;
  }

  return '采集延迟超过 15 秒，正在自动刷新；如持续出现请检查 Collector 运行状态。';
}
