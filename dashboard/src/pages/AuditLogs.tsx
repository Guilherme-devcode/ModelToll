import { useState, useEffect, useRef } from 'react'
import { Search, Filter, ChevronLeft, ChevronRight, Shield, ArrowRight } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { Header } from '../components/layout/Header'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { PageSpinner } from '../components/ui/Spinner'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { mockLogs } from '../api/mock'
import type { AuditLogEntry } from '../types'

const DEMO = import.meta.env.VITE_MOCK === 'true'

function ActionBadge({ action }: { action: AuditLogEntry['action'] }) {
  if (action === 'BLOCKED')     return <Badge variant="red">Blocked</Badge>
  if (action === 'FORWARDED')   return <Badge variant="green">Forwarded</Badge>
  return <Badge variant="gray">Pass-through</Badge>
}

export function AuditLogs() {
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState('')
  const [scrubbedOnly, setScrubbedOnly] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')           // debounced value sent to API
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Debounce search: wait 400ms after typing stops
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setSearch(searchInput)
      setPage(1)
    }, 400)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchInput])

  const { data, loading, error, refetch } = useApi(
    () =>
      DEMO
        ? Promise.resolve(mockLogs)
        : api.logs({
            page,
            page_size: 50,
            action: actionFilter || undefined,
            scrubbed_only: scrubbedOnly || undefined,
            search: search || undefined,
          }),
    [page, actionFilter, scrubbedOnly, search]
  )

  const totalPages = data ? Math.ceil(data.total / 50) : 1

  return (
    <>
      <Header title="Audit Logs" onRefresh={refetch} loading={loading} />
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 max-w-sm">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search user, model, host…"
              className="w-full rounded-lg border border-gray-700 bg-gray-900 pl-9 pr-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-brand-600 focus:outline-none"
            />
          </div>

          <select
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}
            className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-300 focus:border-brand-600 focus:outline-none"
          >
            <option value="">All actions</option>
            <option value="FORWARDED">Forwarded</option>
            <option value="BLOCKED">Blocked</option>
            <option value="PASSTHROUGH">Pass-through</option>
          </select>

          <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={scrubbedOnly}
              onChange={(e) => { setScrubbedOnly(e.target.checked); setPage(1) }}
              className="accent-brand-500"
            />
            <Filter size={13} />
            Scrubbed only
          </label>

          {data && (
            <span className="ml-auto text-xs text-gray-500">
              {data.total.toLocaleString()} total entries
              {search && <span className="ml-1 text-brand-400">· filtered by "{search}"</span>}
            </span>
          )}
        </div>

        {/* Table */}
        <Card padding={false}>
          {loading ? (
            <PageSpinner />
          ) : error ? (
            <p className="p-6 text-sm text-red-400">{error}</p>
          ) : data ? (
            data.items.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-gray-600">
                <Search size={32} className="mb-3 opacity-40" />
                <p className="text-sm">No entries found</p>
                {search && <p className="mt-1 text-xs">Try a different search term</p>}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 text-left">
                      {['Time', 'User', 'Original Model', '→ Routed To', 'Action', 'Scrubbed', 'Tokens', 'Savings', 'Latency'].map((h) => (
                        <th key={h} className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((row) => (
                      <tr key={row.id} className="border-b border-gray-800/50 transition hover:bg-gray-800/30">
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-gray-500 font-mono">
                          {format(parseISO(row.created_at), 'MM/dd HH:mm:ss')}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-400 max-w-[100px] truncate">
                          {row.user_id ?? '—'}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-gray-300 max-w-[140px] truncate">
                          {row.original_model ?? <span className="text-gray-600">unknown</span>}
                        </td>
                        <td className="px-4 py-3">
                          {row.routed_model ? (
                            <span className="flex items-center gap-1 font-mono text-xs text-brand-400">
                              <ArrowRight size={11} className="flex-shrink-0" />
                              {row.routed_model}
                            </span>
                          ) : (
                            <span className="text-gray-600 text-xs">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <ActionBadge action={row.action} />
                        </td>
                        <td className="px-4 py-3">
                          {row.scrubber_triggered ? (
                            <span className="flex items-center gap-1 text-xs text-amber-400">
                              <Shield size={12} />
                              {row.scrubber_detection_count} found
                            </span>
                          ) : (
                            <span className="text-xs text-gray-600">clean</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-400 font-mono whitespace-nowrap">
                          {row.input_tokens.toLocaleString()} / {row.output_tokens.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-xs font-medium text-emerald-400 font-mono">
                          {row.savings_usd > 0 ? `$${row.savings_usd.toFixed(4)}` : '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500 font-mono">
                          {row.latency_ms}ms
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : null}
        </Card>

        {/* Pagination */}
        {data && totalPages > 1 && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">
              Page {page} of {totalPages}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-lg border border-gray-700 p-1.5 text-gray-400 transition hover:border-gray-600 hover:text-gray-200 disabled:opacity-30"
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="rounded-lg border border-gray-700 p-1.5 text-gray-400 transition hover:border-gray-600 hover:text-gray-200 disabled:opacity-30"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
