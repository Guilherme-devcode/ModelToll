import { useState } from 'react'
import { Header } from '../components/layout/Header'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { PageSpinner } from '../components/ui/Spinner'
import { SavingsChart } from '../components/charts/SavingsChart'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import { mockSavings } from '../api/mock'

const DEMO = import.meta.env.VITE_MOCK === 'true'

function fmt$(n: number) {
  return n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${n.toFixed(0)}`
}

export function Savings() {
  const [days, setDays] = useState(30)
  const { data, loading, error, refetch } = useApi(
    () => DEMO ? Promise.resolve(mockSavings) : api.savings('default', days),
    [days]
  )

  const totalSavings = data?.reduce((s, d) => s + d.total_savings_usd, 0) ?? 0
  const totalFee     = data?.reduce((s, d) => s + d.modeltoll_fee_usd, 0) ?? 0
  const totalReqs    = data?.reduce((s, d) => s + d.total_requests, 0) ?? 0

  return (
    <>
      <Header title="Savings & Cost Arbitrage" onRefresh={refetch} loading={loading} />
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">

        {/* Period selector */}
        <div className="flex items-center gap-2">
          {[7, 14, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                days === d
                  ? 'bg-brand-700 text-white'
                  : 'border border-gray-700 text-gray-400 hover:border-gray-600 hover:text-gray-200'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-xl border border-emerald-800/50 bg-emerald-900/20 p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-emerald-600">Client Savings</p>
            <p className="mt-2 text-3xl font-bold text-emerald-400">{fmt$(totalSavings)}</p>
            <p className="mt-1 text-xs text-emerald-700">Last {days} days</p>
          </div>
          <div className="rounded-xl border border-purple-800/50 bg-purple-900/20 p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-purple-600">ModelToll Fee (20%)</p>
            <p className="mt-2 text-3xl font-bold text-purple-400">{fmt$(totalFee)}</p>
            <p className="mt-1 text-xs text-purple-700">Revenue generated</p>
          </div>
          <div className="rounded-xl border border-gray-700 bg-gray-900 p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Requests Processed</p>
            <p className="mt-2 text-3xl font-bold text-gray-200">{totalReqs.toLocaleString()}</p>
            <p className="mt-1 text-xs text-gray-600">Last {days} days</p>
          </div>
        </div>

        {/* Chart */}
        <Card padding={false}>
          <div className="p-5">
            <CardHeader>
              <CardTitle>Daily Savings vs ModelToll Revenue</CardTitle>
              <span className="text-xs text-gray-500">Last {days} days</span>
            </CardHeader>
            {loading
              ? <PageSpinner />
              : error
                ? <p className="text-sm text-red-400">{error}</p>
                : data
                  ? <SavingsChart data={data} />
                  : null
            }
          </div>
        </Card>

        {/* Table */}
        {data && (
          <Card padding={false}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-left">
                    {['Date', 'Requests', 'Source Cost', 'Target Cost', 'Savings', 'ModelToll Fee'].map((h) => (
                      <th key={h} className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...data].reverse().map((row) => (
                    <tr key={row.date} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition">
                      <td className="px-4 py-2.5 font-mono text-xs text-gray-400">{row.date}</td>
                      <td className="px-4 py-2.5 text-xs text-gray-400">{row.total_requests.toLocaleString()}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-red-400">{fmt$(row.source_cost_usd)}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-gray-300">{fmt$(row.target_cost_usd)}</td>
                      <td className="px-4 py-2.5 font-mono text-xs font-semibold text-emerald-400">{fmt$(row.total_savings_usd)}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-purple-400">{fmt$(row.modeltoll_fee_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </>
  )
}
