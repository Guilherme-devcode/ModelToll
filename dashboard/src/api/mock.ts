/**
 * Mock data for development / demo mode (no backend required).
 * Activated when VITE_MOCK=true or when API call fails.
 */
import type { AuditLogPage, DailySavingsItem, ModelUsageItem, Summary } from '../types'
import { subDays, format } from 'date-fns'

export const mockSummary: Summary = {
  period_days: 30,
  total_requests: 48_320,
  forwarded_requests: 45_810,
  blocked_requests: 1_230,
  scrubbed_requests: 12_400,
  total_input_tokens: 142_000_000,
  total_output_tokens: 38_000_000,
  source_cost_usd: 92_400,
  target_cost_usd: 3_100,
  total_savings_usd: 89_300,
  modeltoll_fee_usd: 17_860,
  savings_percent: 96.6,
  top_entity_types: ['EMAIL_ADDRESS', 'AWS_ACCESS_KEY', 'PERSON', 'CPF_BR', 'BEARER_TOKEN'],
}

export const mockTopModels: ModelUsageItem[] = [
  { model: 'gpt-4o',          request_count: 18_400, total_input_tokens: 54_000_000, total_savings_usd: 38_200 },
  { model: 'gpt-4-turbo',     request_count: 12_100, total_input_tokens: 36_000_000, total_savings_usd: 28_900 },
  { model: 'claude-opus-4-6', request_count:  8_200, total_input_tokens: 24_000_000, total_savings_usd: 14_600 },
  { model: 'claude-sonnet-4-6', request_count: 5_100, total_input_tokens: 15_000_000, total_savings_usd:  5_300 },
  { model: 'gemini-1.5-pro',  request_count:  4_520, total_input_tokens: 13_000_000, total_savings_usd:  2_300 },
]

export const mockSavings: DailySavingsItem[] = Array.from({ length: 30 }, (_, i) => {
  const base = 2800 + Math.sin(i * 0.4) * 600 + Math.random() * 400
  const fee = base * 0.2
  return {
    date: format(subDays(new Date(), 29 - i), 'yyyy-MM-dd'),
    total_requests: Math.floor(1400 + Math.random() * 400),
    total_savings_usd: Math.round(base),
    modeltoll_fee_usd: Math.round(fee),
    source_cost_usd: Math.round(base + 150 + Math.random() * 200),
    target_cost_usd: Math.round(150 + Math.random() * 200),
  }
})

const actions = ['FORWARDED', 'FORWARDED', 'FORWARDED', 'BLOCKED', 'FORWARDED'] as const
const hosts   = ['api.openai.com', 'api.anthropic.com', 'api.openai.com', 'api.groq.com']
const models  = ['gpt-4o', 'gpt-4-turbo', 'claude-opus-4-6', 'claude-sonnet-4-6', 'gpt-4-turbo']
const routed  = ['gpt-4o-mini', 'gpt-4o-mini', 'claude-haiku-4-5-20251001', 'claude-haiku-4-5-20251001', 'gpt-4o-mini']
const types   = [['AWS_ACCESS_KEY'], ['EMAIL_ADDRESS', 'PERSON'], null, ['CPF_BR'], null]

export const mockLogs: AuditLogPage = {
  total: 48_320,
  page: 1,
  page_size: 50,
  items: Array.from({ length: 50 }, (_, i) => {
    const idx = i % 5
    const scrubbed = types[idx] !== null
    return {
      id: `00000000-0000-0000-0000-${String(i).padStart(12, '0')}`,
      created_at: subDays(new Date(), Math.floor(i / 5)).toISOString(),
      tenant_id: 'default',
      user_id: `user-${(i % 12) + 1}`,
      original_host: hosts[idx % hosts.length],
      original_model: models[idx],
      action: actions[idx],
      routed_model: actions[idx] !== 'BLOCKED' ? routed[idx] : null,
      routed_provider: actions[idx] !== 'BLOCKED' ? (idx < 2 ? 'openai' : 'anthropic') : null,
      scrubber_triggered: scrubbed,
      scrubber_detection_count: scrubbed ? (types[idx]?.length ?? 0) : 0,
      scrubber_entity_types: types[idx],
      input_tokens: 800 + Math.floor(Math.random() * 3200),
      output_tokens: 200 + Math.floor(Math.random() * 800),
      savings_usd: actions[idx] !== 'BLOCKED' ? parseFloat((1.2 + Math.random() * 4).toFixed(4)) : 0,
      savings_percent: actions[idx] !== 'BLOCKED' ? 94 + Math.random() * 4 : 0,
      latency_ms: 120 + Math.floor(Math.random() * 600),
      response_status: actions[idx] !== 'BLOCKED' ? 200 : null,
    }
  }),
}
