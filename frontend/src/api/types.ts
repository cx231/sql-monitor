import type { InstanceItem } from '@/stores/instances';

export interface DashboardMetrics {
  session_count: number;
  active_request_count: number;
  blocked_session_count: number;
  root_blocker_count: number;
  max_blocking_duration_ms: number;
  waiting_request_count: number;
  deadlocks_last_hour: number;
}

export interface TopWait {
  wait_type: string;
  wait_category: string;
  waiting_tasks_count: number;
  total_wait_time_ms: number;
  max_wait_time_ms: number;
}

export interface SqlListItem {
  session_id: number;
  request_id: number | null;
  database_name: string | null;
  status: string | null;
  command: string | null;
  duration_ms: number | null;
  cpu_time_ms: number | null;
  logical_reads: number | null;
  reads: number | null;
  writes: number | null;
  wait_type: string | null;
  wait_time_ms: number | null;
  blocking_session_id: number | null;
  sql_hash: string | null;
  normalized_sql_hash: string | null;
  sql_preview: string | null;
  sql_text: string | null;
}

export interface ResourceTrendPoint {
  snapshot_time: string;
  cpu_load_percent: number | null;
  memory_usage_percent: number | null;
  network_rate_bytes_per_sec: number | null;
}

export interface DashboardOut {
  instance_id: string;
  frame_id: string;
  snapshot_time: string;
  collect_delay_seconds: number;
  metrics_window_minutes: number;
  metrics: DashboardMetrics;
  resource_trends: ResourceTrendPoint[];
  top_waits: TopWait[];
  top_cpu_sqls: SqlListItem[];
  top_io_sqls: SqlListItem[];
  top_tempdb_sessions: unknown[];
  recent_events: unknown[];
}

export interface SessionListItem {
  session_id: number;
  login_name: string | null;
  host_name: string | null;
  program_name: string | null;
  database_name: string | null;
  status: string | null;
  open_transaction_count: number;
  cpu_time: number | null;
  reads: number | null;
  writes: number | null;
  logical_reads: number | null;
  wait_type: string | null;
  wait_time_ms: number | null;
  blocking_session_id: number | null;
  current_sql_hash: string | null;
  current_sql_preview: string | null;
}

export interface PageOut<T> {
  instance_id: string;
  frame_id: string;
  snapshot_time: string;
  page: number;
  page_size: number;
  total: number;
  items: T[];
}

export interface BlockingNode {
  blocking_session_id: number | null;
  blocked_session_id: number;
  chain_depth: number;
  wait_type: string | null;
  wait_time_ms: number | null;
  resource_description: string | null;
  cycle_detected: boolean;
  special_blocker_code: number | null;
}

export type RiskLevel = 'low' | 'medium' | 'high';

export interface BlockingChain {
  root_session_id: number | null;
  blocked_count: number;
  max_wait_time_ms: number;
  risk_level: RiskLevel;
  nodes: BlockingNode[];
}

export interface BlockingOut {
  instance_id: string;
  frame_id: string;
  snapshot_time: string;
  chains: BlockingChain[];
}

export interface ReplayFrameOut {
  instance_id: string;
  requested_time: string;
  snapshot_time: string;
  frame_id: string;
  dashboard: DashboardOut;
  sessions: SessionListItem[];
  sqls: SqlListItem[];
  blocking: BlockingChain[];
  waits: TopWait[];
  tempdb: unknown[];
}

export interface KillResponse {
  audit_id: string;
  instance_id: string;
  session_id: number;
  result: 'success' | 'failed' | 'rejected';
  error_message: string | null;
}

export type { InstanceItem };
