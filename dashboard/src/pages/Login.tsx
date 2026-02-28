import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, Eye, EyeOff, LogIn, AlertCircle } from 'lucide-react'
import { api } from '../api/client'

export function Login() {
  const [key, setKey] = useState('')
  const [show, setShow] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!key.trim()) return
    setLoading(true)
    setError(null)
    try {
      localStorage.setItem('mt_admin_key', key.trim())
      await api.health()
      navigate('/', { replace: true })
    } catch (err) {
      localStorage.removeItem('mt_admin_key')
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setError(msg === '403' ? 'Invalid API key. Check your X-Admin-Api-Key.' : `Connection failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 shadow-lg shadow-brand-900/50">
            <Shield size={28} className="text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-100">ModelToll</h1>
            <p className="mt-1 text-sm text-gray-500">AI Gateway Admin Dashboard</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="rounded-xl border border-gray-800 bg-gray-900 p-6 shadow-xl">
          <h2 className="mb-5 text-sm font-semibold text-gray-300">Enter your admin API key to continue</h2>

          <div className="relative">
            <input
              type={show ? 'text' : 'password'}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="X-Admin-Api-Key"
              autoFocus
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 pr-10 font-mono text-sm text-gray-100 placeholder-gray-600 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500/30"
            />
            <button
              type="button"
              onClick={() => setShow((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition"
            >
              {show ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>

          {error && (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-800/50 bg-red-900/20 px-3 py-2.5">
              <AlertCircle size={14} className="mt-0.5 flex-shrink-0 text-red-400" />
              <p className="text-xs text-red-400">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !key.trim()}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            ) : (
              <LogIn size={15} />
            )}
            {loading ? 'Verifying…' : 'Sign In'}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-gray-600">
          Key is stored locally in your browser. Never share it.
        </p>
      </div>
    </div>
  )
}
