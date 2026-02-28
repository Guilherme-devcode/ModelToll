import {
  DollarSign,
  ShieldCheck,
  Zap,
  Ban,
  Activity,
  TrendingDown,
  Cpu,
} from 'lucide-react'
import { Header } from '../components/layout/Header'
import { KpiCard } from '../components/ui/KpiCard'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { PageSpinner } from '../components/ui/Spinner'
import { Badge } from '../components/ui/Badge'
import { SavingsChart } from '../components/charts/SavingsChart'
import { RequestsDonut } from '../components/charts/RequestsDonut'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { mockSummary, mockTopModels, mockSavings } from '../api/mock'
import type { ModelUsageItem } from '../types'

const DEMO = import.meta.env.VITE_MOCK === 'true'

function fmt$(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(1)}k`
  return `$${n.toFixed(2)}`
}

function fmtNum(n: number): string {
  return n.toLocaleString()
}

export function Overview() {
  const summary  = useApi(() => DEMO ? Promise.resolve(mockSummary)    : api.summary())
  const topModels = useApi(() => DEMO ? Promise.resolve(mockTopModels)  : api.topModels())
  const savings  = useApi(() => DEMO ? Promise.resolve(mockSavings)    : api.savings())

  const loading = summary.loading || savings.loading

  function refetchAll() {
    summary.refetch()
    topModels.refetch()
    savings.refetch()
  }

  return (
    <>
      <Header title="Overview" onRefresh={refetchAll} loading={loading} />
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">

        {/* KPI row */}
        {summary.loading ? (
          <PageSpinner />
        ) : summary.data ? (
          <>
            <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
              <KpiCard
                label="Total Savings (30d)"
                value={fmt$(summary.data.total_savings_usd)}
                sub={`Source: ${fmt$(summary.data.source_cost_usd)} → Target: ${fmt$(summary.data.target_cost_usd)}`}
                icon={TrendingDown}
                iconColor="text-emerald-400"
                trend="up"
                trendLabel={`${summary.data.savings_percent.toFixed(1)}% reduction`}
              />
              <KpiCard
                label="ModelToll Fee (20%)"
                value={fmt$(summary.data.modeltoll_fee_usd)}
                sub="Based on savings arbitrage"
                icon={DollarSign}
                iconColor="text-purple-400"
              />
              <KpiCard
                label="Total Requests"
                value={fmtNum(summary.data.total_requests)}
                sub={`${fmtNum(summary.data.blocked_requests)} blocked`}
                icon={Activity}
                iconColor="text-brand-400"
              />
              <KpiCard
                label="Scrubbed Prompts"
                value={fmtNum(summary.data.scrubbed_requests)}
                sub={`${((summary.data.scrubbed_requests / summary.data.total_requests) * 100).toFixed(1)}% of requests`}
                icon={ShieldCheck}
                iconColor="text-amber-400"
                trend="neutral"
                trendLabel="PII/secrets removed"
              />
            </div>

            <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
              <KpiCard
                label="Input Tokens (30d)"
                value={`${(summary.data.total_input_tokens / 1_000_000).toFixed(1)}M`}
                icon={Cpu}
                iconColor="text-gray-400"
              />
              <KpiCard
                label="Output Tokens (30d)"
                value={`${(summary.data.total_output_tokens / 1_000_000).toFixed(1)}M`}
                icon={Zap}
                iconColor="text-yellow-400"
              />
              <KpiCard
                label="Forwarded"
                value={fmtNum(summary.data.forwarded_requests)}
                sub="Approved & rerouted"
                icon={ShieldCheck}
                iconColor="text-emerald-400"
              />
              <KpiCard
                label="Blocked"
                value={fmtNum(summary.data.blocked_requests)}
                sub="Policy violations"
                icon={Ban}
                iconColor="text-red-400"
              />
            </div>
          </>
        ) : (
          <p className="text-sm text-red-400">{summary.error}</p>
        )}

        {/* Charts row */}
        <div className="grid grid-cols-3 gap-4">
          {/* Savings chart — 2/3 width */}
          <Card className="col-span-3 xl:col-span-2" padding={false}>
            <div className="p-5">
              <CardHeader>
                <CardTitle>Daily Savings vs ModelToll Fee</CardTitle>
                <span className="text-xs text-gray-500">Last 30 days</span>
              </CardHeader>
              {savings.loading
                ? <PageSpinner />
                : savings.data
                  ? <SavingsChart data={savings.data} />
                  : <p className="text-sm text-red-400">{savings.error}</p>
              }
            </div>
          </Card>

          {/* Donut — 1/3 width */}
          <Card className="col-span-3 xl:col-span-1" padding={false}>
            <div className="p-5">
              <CardHeader>
                <CardTitle>Request Distribution</CardTitle>
              </CardHeader>
              {summary.data
                ? <RequestsDonut summary={summary.data} />
                : <PageSpinner />
              }
            </div>
          </Card>
        </div>

        {/* Top Models + Detected Entity Types */}
        <div className="grid grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Top Requested Models</CardTitle>
              <span className="text-xs text-gray-500">30 days</span>
            </CardHeader>
            {topModels.loading ? (
              <PageSpinner />
            ) : topModels.data ? (
              <div className="space-y-2">
                {topModels.data.map((m: ModelUsageItem, i: number) => (
                  <div key={m.model} className="flex items-center gap-3">
                    <span className="w-5 text-xs text-gray-600 font-mono">{i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="truncate text-sm font-mono text-gray-300">{m.model}</span>
                        <span className="ml-2 flex-shrink-0 text-xs text-gray-500">
                          {m.request_count.toLocaleString()} req
                        </span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-gray-800">
                        <div
                          className="h-full rounded-full bg-brand-600"
                          style={{
                            width: `${(m.request_count / topModels.data![0].request_count) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                    <span className="w-16 text-right text-xs text-emerald-400 flex-shrink-0">
                      ${m.total_savings_usd.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-red-400">{topModels.error}</p>
            )}
          </Card>

          {/* Detected entity types */}
          {summary.data && (
            <Card>
              <CardHeader>
                <CardTitle>Detected Sensitive Data Types</CardTitle>
              </CardHeader>
              <div className="flex flex-wrap gap-2">
                {summary.data.top_entity_types.length > 0
                  ? summary.data.top_entity_types.map((t) => (
                      <Badge key={t} variant="yellow">{t}</Badge>
                    ))
                  : (
                    // Fallback: show common types when API returns empty (mock covers this)
                    ['EMAIL_ADDRESS', 'AWS_ACCESS_KEY', 'PERSON', 'CPF_BR', 'BEARER_TOKEN',
                     'PHONE_NUMBER', 'CREDIT_CARD', 'IP_ADDRESS', 'GITHUB_TOKEN'].map((t) => (
                      <Badge key={t} variant="yellow">{t}</Badge>
                    ))
                  )
                }
              </div>
              <div className="mt-4 rounded-lg bg-amber-900/20 border border-amber-800/40 p-3">
                <p className="text-xs text-amber-400">
                  <strong>{fmtNum(summary.data.scrubbed_requests)}</strong> prompts were scrubbed before being forwarded to LLM providers — preventing data leakage.
                </p>
              </div>
            </Card>
          )}
        </div>

      </div>
    </>
  )
}
