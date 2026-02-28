export interface Summary {
  period_days: number
  total_requests: number
  forwarded_requests: number
  blocked_requests: number
  scrubbed_requests: number
  total_input_tokens: number
  total_output_tokens: number
  source_cost_usd: number
  target_cost_usd: number
  total_savings_usd: number
  modeltoll_fee_usd: number
  savings_percent: number
  top_entity_types: string[]
}

export interface AuditLogEntry {
  id: string
  created_at: string
  tenant_id: string
  user_id: string | null
  original_host: string
  original_model: string | null
  action: 'FORWARDED' | 'BLOCKED' | 'PASSTHROUGH'
  routed_model: string | null
  routed_provider: string | null
  scrubber_triggered: boolean
  scrubber_detection_count: number
  scrubber_entity_types: string[] | null
  input_tokens: number
  output_tokens: number
  savings_usd: number
  savings_percent: number
  latency_ms: number
  response_status: number | null
}

export interface AuditLogPage {
  total: number
  page: number
  page_size: number
  items: AuditLogEntry[]
}

export interface ModelUsageItem {
  model: string
  request_count: number
  total_input_tokens: number
  total_savings_usd: number
}

export interface DailySavingsItem {
  date: string
  total_requests: number
  total_savings_usd: number
  modeltoll_fee_usd: number
  source_cost_usd: number
  target_cost_usd: number
}
