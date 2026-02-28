import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import type { DailySavingsItem } from '../../types'
import { format, parseISO } from 'date-fns'

interface Props {
  data: DailySavingsItem[]
}

function fmt(v: number) {
  return v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`
}

export function SavingsChart({ data }: Props) {
  const formatted = data.map((d) => ({
    ...d,
    dateLabel: format(parseISO(d.date), 'MMM dd'),
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={formatted} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="savingsGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#318bff" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#318bff" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="feeGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#a78bfa" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis
          dataKey="dateLabel"
          tick={{ fill: '#6b7280', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          interval={4}
        />
        <YAxis
          tickFormatter={fmt}
          tick={{ fill: '#6b7280', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={50}
        />
        <Tooltip
          contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
          labelStyle={{ color: '#e5e7eb', fontSize: 12 }}
          formatter={(v: number, name: string) => [
            `$${v.toLocaleString()}`,
            name === 'total_savings_usd' ? 'Savings' : 'ModelToll Fee',
          ]}
        />
        <Legend
          formatter={(v) => (
            <span className="text-xs text-gray-400">
              {v === 'total_savings_usd' ? 'Client Savings' : 'ModelToll Fee (20%)'}
            </span>
          )}
        />
        <Area
          type="monotone"
          dataKey="total_savings_usd"
          stroke="#318bff"
          strokeWidth={2}
          fill="url(#savingsGrad)"
          dot={false}
          activeDot={{ r: 4, fill: '#318bff' }}
        />
        <Area
          type="monotone"
          dataKey="modeltoll_fee_usd"
          stroke="#a78bfa"
          strokeWidth={2}
          fill="url(#feeGrad)"
          dot={false}
          activeDot={{ r: 4, fill: '#a78bfa' }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
