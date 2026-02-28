import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  ScrollText,
  GitBranch,
  TrendingDown,
  Settings,
  Shield,
  ChevronRight,
} from 'lucide-react'
import { clsx } from 'clsx'

const nav = [
  { to: '/',        label: 'Overview',   icon: LayoutDashboard },
  { to: '/logs',    label: 'Audit Logs', icon: ScrollText },
  { to: '/models',  label: 'Models',     icon: GitBranch },
  { to: '/savings', label: 'Savings',    icon: TrendingDown },
  { to: '/settings',label: 'Settings',   icon: Settings },
]

export function Sidebar() {
  return (
    <aside className="flex w-60 flex-col border-r border-gray-800 bg-gray-950">
      {/* Logo */}
      <div className="flex items-center gap-3 border-b border-gray-800 px-5 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
          <Shield size={16} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-bold text-gray-100">ModelToll</p>
          <p className="text-xs text-gray-500">AI Gateway</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              clsx(
                'group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-brand-900/60 text-brand-300'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
              )
            }
          >
            {({ isActive }) => (
              <>
                <span className="flex items-center gap-3">
                  <Icon size={16} />
                  {label}
                </span>
                {isActive && <ChevronRight size={14} className="opacity-60" />}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-800 px-5 py-3">
        <p className="text-xs text-gray-600">v0.1.0 · © 2026 ModelToll</p>
      </div>
    </aside>
  )
}
