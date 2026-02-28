import { Header } from '../components/layout/Header'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { PageSpinner } from '../components/ui/Spinner'
import { Badge } from '../components/ui/Badge'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { mockTopModels } from '../api/mock'

const DEMO = import.meta.env.VITE_MOCK === 'true'

const ROUTING_TABLE = [
  { source: 'gpt-4o',          target: 'gpt-4o-mini',           provider: 'OpenAI',    savings: '97%' },
  { source: 'gpt-4-turbo',     target: 'gpt-4o-mini',           provider: 'OpenAI',    savings: '98%' },
  { source: 'claude-opus',     target: 'claude-haiku',          provider: 'Anthropic', savings: '95%' },
  { source: 'claude-sonnet',   target: 'claude-haiku',          provider: 'Anthropic', savings: '73%' },
  { source: 'gemini-1.5-pro',  target: 'gemini-1.5-flash',      provider: 'Google',    savings: '98%' },
]

export function Models() {
  const { data, loading, error, refetch } = useApi(
    () => DEMO ? Promise.resolve(mockTopModels) : api.topModels()
  )

  return (
    <>
      <Header title="Model Usage & Routing" onRefresh={refetch} loading={loading} />
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">

        {/* Usage table */}
        <Card>
          <CardHeader>
            <CardTitle>Requested Models (30 days)</CardTitle>
          </CardHeader>
          {loading ? (
            <PageSpinner />
          ) : error ? (
            <p className="text-sm text-red-400">{error}</p>
          ) : data ? (
            <div className="space-y-3">
              {data.map((m, i) => (
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
                        style={{ width: `${(m.request_count / data[0].request_count) * 100}%` }}
                      />
                    </div>
                    <p className="mt-1 text-xs text-gray-600">
                      {(m.total_input_tokens / 1_000_000).toFixed(1)}M input tokens
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </Card>

        {/* Routing rules */}
        <Card padding={false}>
          <div className="p-5 pb-3">
            <CardHeader>
              <CardTitle>Active Routing Rules</CardTitle>
              <Badge variant="green">Live</Badge>
            </CardHeader>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-y border-gray-800 text-left">
                  {['Requested Model', 'Routed To', 'Provider', 'Cost Reduction', 'Status'].map((h) => (
                    <th key={h} className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROUTING_TABLE.map((r) => (
                  <tr key={r.source} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition">
                    <td className="px-4 py-3 font-mono text-sm text-gray-300">{r.source}*</td>
                    <td className="px-4 py-3 font-mono text-sm text-brand-400">{r.target}</td>
                    <td className="px-4 py-3">
                      <Badge variant={r.provider === 'OpenAI' ? 'green' : r.provider === 'Anthropic' ? 'purple' : 'blue'}>
                        {r.provider}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 font-semibold text-emerald-400">{r.savings}</td>
                    <td className="px-4 py-3">
                      <Badge variant="green">Active</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-4 py-3 text-xs text-gray-600">* Pattern-matched — covers all versioned variants (e.g. gpt-4o-2024-11-20)</p>
        </Card>
      </div>
    </>
  )
}
