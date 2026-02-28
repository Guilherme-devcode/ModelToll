import type { AuditLogPage, DailySavingsItem, ModelUsageItem, Summary } from '../types'

const BASE = ''  // proxied via Vite dev server → http://localhost:8080

function apiKey(): string {
  const stored = localStorage.getItem('mt_admin_key')
  if (stored) return stored
  const fallback = import.meta.env.VITE_DEFAULT_API_KEY
  return typeof fallback === 'string' ? fallback : ''
}

async function get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  }
  const key = apiKey()
  let res = await fetch(url.toString(), {
    headers: { 'X-Admin-Api-Key': key },
  })
  if (res.status === 403) {
    const text = await res.text().catch(() => res.statusText)
    if (text.includes('Invalid admin API key') && localStorage.getItem('mt_admin_key')) {
      localStorage.removeItem('mt_admin_key')
      res = await fetch(url.toString(), {
        headers: { 'X-Admin-Api-Key': apiKey() },
      })
    }
  }
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
  }) => get<AuditLogPage>('/dashboard/logs', params as Record<string, string | number | boolean>),

  topModels: (tenant_id = 'default', days = 30) =>
    get<ModelUsageItem[]>('/dashboard/top-models', { tenant_id, days }),

  savings: (tenant_id = 'default', days = 30) =>
    get<DailySavingsItem[]>('/dashboard/savings', { tenant_id, days }),
}
