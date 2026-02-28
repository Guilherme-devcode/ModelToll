import { Component, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  message: string
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-gray-950 px-4">
          <div className="w-full max-w-sm rounded-xl border border-red-800/50 bg-red-900/20 p-8 text-center">
            <div className="mb-4 flex justify-center">
              <AlertTriangle size={36} className="text-red-400" />
            </div>
            <h2 className="text-lg font-semibold text-red-300">Something went wrong</h2>
            <p className="mt-2 text-sm text-red-400/80">{this.state.message}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-6 rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-600"
            >
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
