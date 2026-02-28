import type {
  AuditLogPage,
  DailySavingsItem,
  GatewayConfig,
  ModelUsageItem,
  RoutingRulesResponse,
  Summary,
} from '../types'

const BASE = ''  // proxied via Vite dev server -> http://localhost:8080

export function apiKey(): string {
  const stored = localStorage.getItem('mt_admin_key')
  if (stored) return stored
  const fallback = import.meta.env.VITE_DEFAULT_API_KEY
  return typeof fallback === 'string' ? fallback : ''
}

export function isAuthenticated(): boolean {
  return apiKey().length > 0
}

export function logout(): void {
  localStorage.removeItem('mt_admin_key')
}

async function get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        url.searchParams.set(k, String(v))
      }
    })
  }
  const res = await fetch(url.toString(), {
    headers: { 'X-Admin-Api-Key': apiKey() },
  })
  if (res.status === 403) throw new Error('403')
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'PATCH',
    headers: {
      'X-Admin-Api-Key': apiKey(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (res.status === 403) throw new Error('403')
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => get<{ status: string; version: string }>('/health'),

  summary: (tenant_id = 'default', days = 30) =>
    get<Summary>('/dashboard/summary', { tenant_id, days }),

  logs: (params: {
    tenant_id?: string
    page?: number
    page_size?: number
    action?: string
    scrubbed_only?: boolean
    search?: string
  }) => get<AuditLogPage>('/dashboard/logs', params as Record<string, string | number | boolean>),

  topModels: (tenant_id = 'default', days = 30) =>
    get<ModelUsageItem[]>('/dashboard/top-models', { tenant_id, days }),

  savings: (tenant_id = 'default', days = 30) =>
    get<DailySavingsItem[]>('/dashboard/savings', { tenant_id, days }),

  routingRules: () =>
    get<RoutingRulesResponse>('/dashboard/routing-rules'),

  getConfig: () =>
    get<GatewayConfig>('/dashboard/config'),

  patchConfig: (body: Partial<GatewayConfig>) =>
    patch<GatewayConfig>('/dashboard/config', body),
}
