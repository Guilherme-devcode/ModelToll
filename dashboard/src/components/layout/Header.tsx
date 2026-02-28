import { RefreshCw, Bell, User } from 'lucide-react'

interface HeaderProps {
  title: string
  onRefresh?: () => void
  loading?: boolean
}

export function Header({ title, onRefresh, loading }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-gray-800 bg-gray-950 px-6 py-4">
      <h1 className="text-lg font-semibold text-gray-100">{title}</h1>
      <div className="flex items-center gap-3">
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-400 transition hover:border-gray-600 hover:text-gray-200 disabled:opacity-50"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        )}
        <button className="rounded-lg border border-gray-800 p-1.5 text-gray-500 hover:text-gray-300 transition">
          <Bell size={16} />
        </button>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-700 text-xs font-bold text-white">
          <User size={14} />
        </div>
      </div>
    </header>
  )
}
