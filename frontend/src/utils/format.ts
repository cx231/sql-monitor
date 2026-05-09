export function formatNullable(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-';
  }

  return String(value);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-';
  }

  return new Intl.NumberFormat('zh-CN').format(value);
}

export function formatDurationMs(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '-';
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)} 秒`;
  }

  return `${value} ms`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

export function toIsoString(value: Date): string {
  return value.toISOString();
}

export function staleSeconds(snapshotTime: string | null | undefined): number | null {
  if (!snapshotTime) {
    return null;
  }

  const time = new Date(snapshotTime).getTime();
  if (Number.isNaN(time)) {
    return null;
  }

  return Math.max(0, Math.floor((Date.now() - time) / 1000));
}
