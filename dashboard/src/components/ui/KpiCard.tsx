import { type LucideIcon } from 'lucide-react'
import { clsx } from 'clsx'

interface KpiCardProps {
  label: string
  value: string
  sub?: string
  icon: LucideIcon
  iconColor?: string
  trend?: 'up' | 'down' | 'neutral'
  trendLabel?: string
}

export function KpiCard({ label, value, sub, icon: Icon, iconColor = 'text-brand-400', trend, trendLabel }: KpiCardProps) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">{label}</p>
          <p className="mt-2 truncate text-2xl font-bold text-gray-100">{value}</p>
          {sub && <p className="mt-1 text-xs text-gray-500">{sub}</p>}
          {trendLabel && (
            <p
              className={clsx(
                'mt-2 text-xs font-medium',
                trend === 'up' && 'text-emerald-400',
                trend === 'down' && 'text-red-400',
                trend === 'neutral' && 'text-gray-400'
              )}
            >
              {trendLabel}
            </p>
          )}
        </div>
        <div className={clsx('rounded-lg bg-gray-800 p-2.5 ml-3 flex-shrink-0', iconColor)}>
          <Icon size={20} />
        </div>
      </div>
    </div>
  )
}
