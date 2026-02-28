import { useState } from 'react'
import { Save, Eye, EyeOff } from 'lucide-react'
import { Header } from '../components/layout/Header'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

export function Settings() {
  const [apiKey, setApiKey] = useState(localStorage.getItem('mt_admin_key') ?? '')
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved] = useState(false)
  const [savingsPct, setSavingsPct] = useState('20')
  const [scrubberOn, setScrubberOn] = useState(true)

  function save() {
    localStorage.setItem('mt_admin_key', apiKey)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <>
      <Header title="Settings" />
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">

        {/* API key */}
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
              onClick={save}
              className="flex items-center gap-2 rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 transition"
            >
              <Save size={14} />
              {saved ? 'Saved!' : 'Save'}
            </button>
          </div>
          <p className="mt-2 text-xs text-gray-600">Stored in localStorage. Sent as <code className="text-gray-400">X-Admin-Api-Key</code> header.</p>
        </Card>

        {/* General settings */}
        <Card>
          <CardHeader>
            <CardTitle>Gateway Settings</CardTitle>
            <Badge variant="gray">Read-only preview</Badge>
          </CardHeader>
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border border-gray-800 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-gray-200">Scrubber Engine</p>
                <p className="text-xs text-gray-500">PII and secrets detection on all prompts</p>
              </div>
              <label className="relative inline-flex cursor-pointer items-center">
                <input type="checkbox" className="sr-only peer" checked={scrubberOn} onChange={(e) => setScrubberOn(e.target.checked)} />
                <div className="peer h-6 w-11 rounded-full bg-gray-700 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:bg-brand-600 peer-checked:after:translate-x-full" />
              </label>
            </div>

            <div className="flex items-center justify-between rounded-lg border border-gray-800 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-gray-200">Savings Share (%)</p>
                <p className="text-xs text-gray-500">ModelToll's cut of the savings</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={savingsPct}
                  onChange={(e) => setSavingsPct(e.target.value)}
                  min="0"
                  max="50"
                  className="w-20 rounded-lg border border-gray-700 bg-gray-800 px-2 py-1 text-right text-sm font-mono text-gray-200 focus:border-brand-600 focus:outline-none"
                />
                <span className="text-sm text-gray-500">%</span>
              </div>
            </div>

            <div className="flex items-center justify-between rounded-lg border border-gray-800 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-gray-200">Default Approved Model</p>
                <p className="text-xs text-gray-500">Fallback when no route matches</p>
              </div>
              <code className="rounded bg-gray-800 px-2 py-1 text-xs text-brand-400">gpt-4o-mini</code>
            </div>
          </div>
        </Card>

        {/* Config paths */}
        <Card>
          <CardHeader>
            <CardTitle>Configuration Files</CardTitle>
          </CardHeader>
          <div className="space-y-2">
            {[
              { label: 'Model Routing', path: 'config/model_routing.json' },
              { label: 'Custom Patterns', path: 'config/custom_patterns.json' },
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
