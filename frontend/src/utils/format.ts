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

export function formatSnapshotDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const pad = (part: number) => String(part).padStart(2, '0');
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  const seconds = pad(date.getSeconds());
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
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

export function formatSessionStatus(value: string | null | undefined): string {
  const map: Record<string, string> = {
    running: '运行中',
    sleeping: '休眠',
    suspended: '挂起',
    runnable: '可运行',
    background: '后台',
  };

  if (!value) {
    return '-';
  }

  return map[value] ?? value;
}
