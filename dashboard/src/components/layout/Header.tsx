import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, Bell, User, LogOut, ChevronDown } from 'lucide-react'
import { logout } from '../../api/client'

interface HeaderProps {
  title: string
  onRefresh?: () => void
  loading?: boolean
}

export function Header({ title, onRefresh, loading }: HeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

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

        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-1.5 rounded-lg border border-gray-800 px-2 py-1.5 text-gray-400 transition hover:border-gray-700 hover:text-gray-200"
          >
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-700">
              <User size={11} className="text-white" />
            </div>
            <ChevronDown size={12} />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 w-40 rounded-lg border border-gray-700 bg-gray-900 py-1 shadow-xl z-50">
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-400 transition hover:bg-gray-800"
              >
                <LogOut size={14} />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
