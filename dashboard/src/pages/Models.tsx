import { Header } from '../components/layout/Header'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { PageSpinner } from '../components/ui/Spinner'
import { Badge } from '../components/ui/Badge'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { mockTopModels } from '../api/mock'
import type { RoutingRulesResponse } from '../types'

const DEMO = import.meta.env.VITE_MOCK === 'true'

const MOCK_ROUTING: RoutingRulesResponse = {
  routes: [
    { source_pattern: 'gpt-4o', target_model: 'gpt-4o-mini', target_provider: 'openai', target_endpoint: 'https://api.openai.com/v1/chat/completions', cost_input_per_1m_source: 5.0, cost_input_per_1m_target: 0.15, cost_output_per_1m_source: 15.0, cost_output_per_1m_target: 0.60, reason: 'gpt-4o → gpt-4o-mini: 97% cheaper' },
    { source_pattern: 'gpt-4-turbo', target_model: 'gpt-4o-mini', target_provider: 'openai', target_endpoint: 'https://api.openai.com/v1/chat/completions', cost_input_per_1m_source: 10.0, cost_input_per_1m_target: 0.15, cost_output_per_1m_source: 30.0, cost_output_per_1m_target: 0.60, reason: 'gpt-4-turbo → gpt-4o-mini: 98% cheaper' },
    { source_pattern: 'claude-opus', target_model: 'claude-haiku-4-5-20251001', target_provider: 'anthropic', target_endpoint: 'https://api.anthropic.com/v1/messages', cost_input_per_1m_source: 15.0, cost_input_per_1m_target: 0.80, cost_output_per_1m_source: 75.0, cost_output_per_1m_target: 4.0, reason: 'claude-opus → claude-haiku: 95% cheaper' },
    { source_pattern: 'claude-sonnet', target_model: 'claude-haiku-4-5-20251001', target_provider: 'anthropic', target_endpoint: 'https://api.anthropic.com/v1/messages', cost_input_per_1m_source: 3.0, cost_input_per_1m_target: 0.80, cost_output_per_1m_source: 15.0, cost_output_per_1m_target: 4.0, reason: 'claude-sonnet → claude-haiku: 73% cheaper' },
    { source_pattern: 'gemini-1.5-pro', target_model: 'gemini-1.5-flash', target_provider: 'google', target_endpoint: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent', cost_input_per_1m_source: 3.5, cost_input_per_1m_target: 0.075, cost_output_per_1m_source: 10.5, cost_output_per_1m_target: 0.3, reason: 'gemini-1.5-pro → gemini-1.5-flash: 98% cheaper' },
  ],
  default_model: 'gpt-4o-mini',
}

function savingsPct(r: RoutingRulesResponse['routes'][0]): string {
  const src = r.cost_input_per_1m_source + r.cost_output_per_1m_source
  const tgt = r.cost_input_per_1m_target + r.cost_output_per_1m_target
  if (src <= 0) return '—'
  return `${Math.round((1 - tgt / src) * 100)}%`
}

export function Models() {
  const usage   = useApi(() => DEMO ? Promise.resolve(mockTopModels) : api.topModels())
  const routing = useApi(() => DEMO ? Promise.resolve(MOCK_ROUTING)  : api.routingRules())

  function refetchAll() {
    usage.refetch()
    routing.refetch()
  }

  return (
    <>
      <Header title="Model Usage & Routing" onRefresh={refetchAll} loading={usage.loading} />
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">

        {/* Usage */}
        <Card>
          <CardHeader>
            <CardTitle>Requested Models (30 days)</CardTitle>
          </CardHeader>
          {usage.loading ? (
            <PageSpinner />
          ) : usage.error ? (
            <p className="text-sm text-red-400">{usage.error}</p>
          ) : usage.data && usage.data.length > 0 ? (
            <div className="space-y-3">
              {usage.data.map((m, i) => (
                <div key={m.model} className="flex items-center gap-4">
                  <span className="w-5 text-xs text-gray-600 font-mono flex-shrink-0">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono text-sm text-gray-200">{m.model}</span>
                      <div className="flex items-center gap-3 ml-2 flex-shrink-0">
                        <span className="text-xs text-gray-500">{m.request_count.toLocaleString()} requests</span>
                        <span className="text-xs text-emerald-400 font-mono">${m.total_savings_usd.toLocaleString()} saved</span>
                      </div>
                    </div>
                    <div className="h-2 w-full rounded-full bg-gray-800">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-brand-700 to-brand-500"
                        style={{ width: `${(m.request_count / usage.data![0].request_count) * 100}%` }}
                      />
                    </div>
                    <p className="mt-1 text-xs text-gray-600">{(m.total_input_tokens / 1_000_000).toFixed(1)}M input tokens</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-gray-600">No model usage data yet.</p>
          )}
        </Card>

        {/* Routing rules (dynamic) */}
        <Card padding={false}>
          <div className="p-5 pb-3">
            <CardHeader>
              <CardTitle>Active Routing Rules</CardTitle>
              <Badge variant="green">Live</Badge>
            </CardHeader>
            {routing.data && (
              <p className="mb-3 text-xs text-gray-500">
                Default: <code className="text-brand-400">{routing.data.default_model}</code>
              </p>
            )}
          </div>
          {routing.loading ? (
            <div className="px-5 pb-5"><PageSpinner /></div>
          ) : routing.error ? (
            <p className="px-5 pb-5 text-sm text-red-400">{routing.error}</p>
          ) : routing.data ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-y border-gray-800 text-left">
                      {['Source Pattern', 'Routes To', 'Provider', 'Cost Savings', 'Reason'].map((h) => (
                        <th key={h} className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {routing.data.routes.map((r) => (
                      <tr key={r.source_pattern} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition">
                        <td className="px-4 py-3 font-mono text-sm text-gray-300">{r.source_pattern}*</td>
                        <td className="px-4 py-3 font-mono text-sm text-brand-400">{r.target_model}</td>
                        <td className="px-4 py-3">
                          <Badge variant={r.target_provider === 'openai' ? 'green' : r.target_provider === 'anthropic' ? 'purple' : 'blue'}>
                            {r.target_provider}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 font-semibold text-emerald-400">{savingsPct(r)}</td>
                        <td className="px-4 py-3 text-xs text-gray-500 max-w-[240px] truncate">{r.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="px-4 py-3 text-xs text-gray-600">
                * Pattern-matched — covers all versioned variants. Edit <code>config/model_routing.json</code> to update.
              </p>
            </>
          ) : null}
        </Card>
      </div>
    </>
  )
}
