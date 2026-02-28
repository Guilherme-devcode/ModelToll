import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { Summary } from '../../types'

interface Props { summary: Summary }

export function RequestsDonut({ summary }: Props) {
  const data = [
    { name: 'Forwarded',  value: summary.forwarded_requests,  color: '#10b981' },
    { name: 'Scrubbed',   value: summary.scrubbed_requests,   color: '#318bff' },
    { name: 'Blocked',    value: summary.blocked_requests,    color: '#f87171' },
  ]

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={85}
          paddingAngle={3}
          dataKey="value"
          strokeWidth={0}
        >
          {data.map((entry, index) => (
            <Cell key={index} fill={entry.color} opacity={0.85} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
          formatter={(v: number) => [v.toLocaleString(), '']}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(v) => <span className="text-xs text-gray-400">{v}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
