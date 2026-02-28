import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import './index.css'
import { Layout } from './components/layout/Layout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Login } from './pages/Login'
import { Overview } from './pages/Overview'
import { AuditLogs } from './pages/AuditLogs'
import { Models } from './pages/Models'
import { Savings } from './pages/Savings'
import { Settings } from './pages/Settings'
import { isAuthenticated } from './api/client'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <>{children}</>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ErrorBoundary>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Layout>
                  <Routes>
                    <Route path="/"         element={<Overview />} />
                    <Route path="/logs"     element={<AuditLogs />} />
                    <Route path="/models"   element={<Models />} />
                    <Route path="/savings"  element={<Savings />} />
                    <Route path="/settings" element={<Settings />} />
                  </Routes>
                </Layout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  </React.StrictMode>
)
