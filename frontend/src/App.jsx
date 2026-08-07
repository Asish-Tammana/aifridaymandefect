import { useState, useEffect, useCallback } from 'react'
import './App.css'
import Dashboard from './pages/Dashboard'
import Producer from './pages/Producer'
import Analytics from './pages/Analytics'
import Metrics from './pages/Metrics'
import Auth from './pages/Auth'

const API_BASE = 'http://localhost:5000/api'

// ─── Toast System ────────────────────────────────────────────────────────────
function ToastContainer({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>{t.message}</div>
      ))}
    </div>
  )
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
function Sidebar({ activePage, onNavigate, riskThreshold, setRiskThreshold, autoRefresh, setAutoRefresh, refreshSeconds, setRefreshSeconds, user, onLogout }) {
  const navItems = [
    { id: 'dashboard', icon: '🏭', label: 'Live Dashboard' },
    { id: 'producer', icon: '🔄', label: 'Producer' },
    { id: 'analytics', icon: '📊', label: 'Analytics' },
  ]
  if (user?.role === 'ADMIN') {
    navItems.push({ id: 'metrics', icon: '📈', label: 'Metrics & ROI' })
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">🏭</div>
        <div className="sidebar-brand-text">
          <span className="sidebar-brand-name">AI Manufacturing</span>
          <span className="sidebar-brand-sub">Defect Prediction</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <span className="nav-section-label">Navigation</span>
        {navItems.map(item => (
          <button
            key={item.id}
            className={`nav-item ${activePage === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-config">
        <div className="config-label">⚙️ Pipeline Config</div>

        <div className="slider-group">
          <div className="slider-header">
            <span className="slider-label">LLM Risk Threshold</span>
            <span className="slider-value">{riskThreshold.toFixed(2)}</span>
          </div>
          <input
            type="range" min={0.1} max={0.9} step={0.05}
            value={riskThreshold}
            onChange={e => setRiskThreshold(parseFloat(e.target.value))}
          />
        </div>

        <div className="toggle-group">
          <span className="toggle-label">Auto-refresh</span>
          <label className="toggle">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        {autoRefresh && (
          <div className="slider-group">
            <div className="slider-header">
              <span className="slider-label">Refresh interval (s)</span>
              <span className="slider-value">{refreshSeconds}s</span>
            </div>
            <input
              type="range" min={3} max={30} step={1}
              value={refreshSeconds}
              onChange={e => setRefreshSeconds(parseInt(e.target.value))}
            />
          </div>
        )}

        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="status-dot online" />
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>API Connected</span>
        </div>

        <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-color)' }}>
          <div style={{ fontSize: '0.8rem', marginBottom: 8 }}>
            Logged in as <strong>{user?.username}</strong> ({user?.role})
          </div>
          <button className="btn btn-ghost btn-sm" style={{ width: '100%' }} onClick={onLogout}>
            Log Out
          </button>
        </div>
      </div>
    </aside>
  )
}

// ─── App Root ─────────────────────────────────────────────────────────────────
export default function App() {
  const [user, setUser] = useState(null)
  const [activePage, setActivePage] = useState('dashboard')
  const [riskThreshold, setRiskThreshold] = useState(0.5)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshSeconds, setRefreshSeconds] = useState(5)
  const [toasts, setToasts] = useState([])

  const showToast = useCallback((message, type = 'success') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000)
  }, [])

  const sharedProps = { API_BASE, showToast, riskThreshold, autoRefresh, refreshSeconds }

  const pages = {
    dashboard: <Dashboard {...sharedProps} />,
    producer: <Producer {...sharedProps} />,
    analytics: <Analytics {...sharedProps} />,
    metrics: <Metrics {...sharedProps} />,
  }

  if (!user) {
    return (
      <div className="app-layout">
        <Auth API_BASE={API_BASE} onLogin={setUser} showToast={showToast} />
        <ToastContainer toasts={toasts} />
      </div>
    )
  }

  return (
    <div className="app-layout">
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        riskThreshold={riskThreshold}
        setRiskThreshold={setRiskThreshold}
        autoRefresh={autoRefresh}
        setAutoRefresh={setAutoRefresh}
        refreshSeconds={refreshSeconds}
        setRefreshSeconds={setRefreshSeconds}
        user={user}
        onLogout={() => setUser(null)}
      />
      <main className="main-content">
        {pages[activePage]}
      </main>
      <ToastContainer toasts={toasts} />
    </div>
  )
}
