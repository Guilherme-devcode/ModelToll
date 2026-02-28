import { useState, useEffect } from 'react'
import { Save, Eye, EyeOff, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react'
import { Header } from '../components/layout/Header'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { PageSpinner } from '../components/ui/Spinner'
import { api } from '../api/client'
import type { GatewayConfig } from '../types'

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

const DEFAULT_KEY = import.meta.env.VITE_DEFAULT_API_KEY ?? 'change-me-admin-key'

export function Settings() {
  const [apiKey, setApiKey] = useState(localStorage.getItem('mt_admin_key') ?? DEFAULT_KEY)
  const [showKey, setShowKey] = useState(false)
  const [keySaved, setKeySaved] = useState(false)

  const [config, setConfig]     = useState<GatewayConfig | null>(null)
  const [configLoading, setConfigLoading] = useState(true)
  const [configError, setConfigError]     = useState<string | null>(null)
  const [saveState, setSaveState]         = useState<SaveState>('idle')

  useEffect(() => {
    setConfigLoading(true)
    api.getConfig()
      .then((c) => { setConfig(c); setConfigLoading(false) })
      .catch((e: Error) => { setConfigError(e.message); setConfigLoading(false) })
  }, [])

  function saveApiKey() {
    localStorage.setItem('mt_admin_key', apiKey)
    setKeySaved(true)
    setTimeout(() => setKeySaved(false), 2000)
  }

  async function saveConfig(patch: Partial<GatewayConfig>) {
    if (!config) return
    setSaveState('saving')
    try {
      const updated = await api.patchConfig(patch)
      setConfig(updated)
      setSaveState('saved')
      setTimeout(() => setSaveState('idle'), 2000)
    } catch (e) {
      setSaveState('error')
      setTimeout(() => setSaveState('idle'), 3000)
    }
  }

  function handleScrubberToggle(enabled: boolean) {
    if (!config) return
    setConfig({ ...config, scrubber_enabled: enabled })
    saveConfig({ scrubber_enabled: enabled })
  }

  function handleSavingsPctBlur(val: string) {
    const pct = parseFloat(val)
    if (isNaN(pct) || pct < 0 || pct > 100 || !config) return
    if (pct === config.savings_share_percent) return
    setConfig({ ...config, savings_share_percent: pct })
    saveConfig({ savings_share_percent: pct })
  }

  return (
    <>
      <Header title="Settings" />
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">

        {/* Admin API Key */}
        <Card>
          <CardHeader>
            <CardTitle>Admin API Key</CardTitle>
          </CardHeader>
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-md">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 pr-10 font-mono text-sm text-gray-200 focus:border-brand-600 focus:outline-none"
                placeholder="Enter X-Admin-Api-Key"
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
              >
                {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            <button
              onClick={saveApiKey}
              className="flex items-center gap-2 rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 transition"
            >
              {keySaved ? <CheckCircle size={14} /> : <Save size={14} />}
              {keySaved ? 'Saved!' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => { setApiKey(DEFAULT_KEY); localStorage.setItem('mt_admin_key', DEFAULT_KEY); setKeySaved(true); setTimeout(() => setKeySaved(false), 2000) }}
              className="rounded-lg border border-gray-600 px-3 py-2 text-sm text-gray-400 hover:text-gray-200 hover:border-gray-500 transition"
            >
              Use default
            </button>
          </div>
          <p className="mt-2 text-xs text-gray-600">
            Stored in localStorage. Sent as <code className="text-gray-400">X-Admin-Api-Key</code> header.
          </p>
        </Card>

        {/* Gateway Settings */}
        <Card>
          <CardHeader>
            <CardTitle>Gateway Configuration</CardTitle>
            <div className="flex items-center gap-2">
              {saveState === 'saving' && <RefreshCw size={13} className="animate-spin text-gray-400" />}
              {saveState === 'saved'  && <CheckCircle size={13} className="text-emerald-400" />}
              {saveState === 'error'  && <AlertCircle size={13} className="text-red-400" />}
              <span className="text-xs text-gray-500">
                {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved' : saveState === 'error' ? 'Save failed' : 'Auto-saved'}
              </span>
            </div>
          </CardHeader>

          {configLoading ? (
            <PageSpinner />
          ) : configError ? (
            <p className="text-sm text-red-400">{configError}</p>
          ) : config ? (
            <div className="space-y-4">
              {/* Scrubber toggle */}
              <div className="flex items-center justify-between rounded-lg border border-gray-800 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-200">Scrubber Engine</p>
                  <p className="text-xs text-gray-500">PII and secrets detection on all prompts</p>
                </div>
                <label className="relative inline-flex cursor-pointer items-center">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={config.scrubber_enabled}
                    onChange={(e) => handleScrubberToggle(e.target.checked)}
                  />
                  <div className="peer h-6 w-11 rounded-full bg-gray-700 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:bg-brand-600 peer-checked:after:translate-x-full" />
                </label>
              </div>

              {/* Savings share */}
              <div className="flex items-center justify-between rounded-lg border border-gray-800 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-200">Savings Share (%)</p>
                  <p className="text-xs text-gray-500">ModelToll's fee as % of monthly savings</p>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    defaultValue={config.savings_share_percent}
                    onBlur={(e) => handleSavingsPctBlur(e.target.value)}
                    min="0"
                    max="50"
                    step="1"
                    className="w-20 rounded-lg border border-gray-700 bg-gray-800 px-2 py-1 text-right text-sm font-mono text-gray-200 focus:border-brand-600 focus:outline-none"
                  />
                  <span className="text-sm text-gray-500">%</span>
                </div>
              </div>

              {/* Default model */}
              <div className="flex items-center justify-between rounded-lg border border-gray-800 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-200">Default Approved Model</p>
                  <p className="text-xs text-gray-500">Fallback when no routing rule matches</p>
                </div>
                <code className="rounded bg-gray-800 px-2 py-1 text-xs text-brand-400">{config.default_approved_model}</code>
              </div>

              {/* Monitored hosts */}
              <div className="rounded-lg border border-gray-800 px-4 py-3">
                <p className="mb-2 text-sm font-medium text-gray-200">Monitored AI Hosts</p>
                <div className="flex flex-wrap gap-1.5">
                  {config.monitored_ai_hosts.map((h) => (
                    <code key={h} className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400">{h}</code>
                  ))}
                </div>
              </div>

              {/* PII entities */}
              <div className="rounded-lg border border-gray-800 px-4 py-3">
                <p className="mb-2 text-sm font-medium text-gray-200">Detected PII Types</p>
                <div className="flex flex-wrap gap-1.5">
                  {config.pii_entities.map((e) => (
                    <span key={e} className="rounded bg-amber-900/30 border border-amber-800/40 px-2 py-0.5 text-xs text-amber-400">{e}</span>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </Card>

        {/* Config files */}
        <Card>
          <CardHeader>
            <CardTitle>Configuration Files</CardTitle>
          </CardHeader>
          <div className="space-y-2">
            {[
              { label: 'Model Routing Rules', path: 'config/model_routing.json' },
              { label: 'Custom Detection Patterns', path: 'config/custom_patterns.json' },
            ].map(({ label, path }) => (
              <div key={path} className="flex items-center justify-between rounded-lg border border-gray-800 px-4 py-3">
                <span className="text-sm text-gray-300">{label}</span>
                <code className="text-xs text-gray-500 font-mono">{path}</code>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  )
}
