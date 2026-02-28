import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import { Layout } from './components/layout/Layout'
import { Overview } from './pages/Overview'
import { AuditLogs } from './pages/AuditLogs'
import { Models } from './pages/Models'
import { Savings } from './pages/Savings'
import { Settings } from './pages/Settings'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/"        element={<Overview />} />
          <Route path="/logs"    element={<AuditLogs />} />
          <Route path="/models"  element={<Models />} />
          <Route path="/savings" element={<Savings />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  </React.StrictMode>
)
