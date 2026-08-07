import { useState, useEffect, useCallback } from 'react'

// ─── Preview Table ────────────────────────────────────────────────────────────
function PreviewTable({ rows }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🎉</div>
        <div className="empty-state-title">All batches have been pushed!</div>
        <p>Hit Reset to start over.</p>
      </div>
    )
  }
  const cols = Object.keys(rows[0])
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>{cols.map(c => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={row.ground_truth_label === 'FAILURE' ? 'row-high' : 'row-low'}>
              {cols.map(c => (
                <td key={c}>
                  {c === 'ground_truth_label'
                    ? <span className={`badge badge-${row[c] === 'FAILURE' ? 'high' : 'low'}`}>{row[c]}</span>
                    : (row[c] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Bar Chart ────────────────────────────────────────────────────────────────
function MiniBarChart({ data, colorVar = '--accent' }) {
  if (!data || Object.keys(data).length === 0) return <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>No data</p>
  const max = Math.max(...Object.values(data))
  return (
    <div className="chart-bar-wrap">
      {Object.entries(data)
        .sort((a, b) => b[1] - a[1])
        .map(([label, count]) => (
          <div key={label} className="chart-bar-item">
            <span className="chart-bar-label">{label}</span>
            <div className="chart-bar-track">
              <div
                className="chart-bar-fill"
                style={{ width: `${(count / max) * 100}%`, background: `var(${colorVar})` }}
              >
                <span className="chart-bar-count">{count}</span>
              </div>
            </div>
          </div>
        ))}
    </div>
  )
}

// ─── Producer Page ────────────────────────────────────────────────────────────
export default function Producer({ API_BASE, showToast }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [pushing, setPushing] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [batchSize, setBatchSize] = useState(5)
  const [expandStats, setExpandStats] = useState(false)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/producer/status`)
      if (!res.ok) {
        const err = await res.json()
        showToast(err.error || 'Failed to load producer status', 'error')
        return
      }
      const json = await res.json()
      setStatus(json)
    } catch (e) {
      showToast(`Connection error: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }, [API_BASE, showToast])

  useEffect(() => { fetchStatus() }, [fetchStatus])

  const pushBatch = async () => {
    setPushing(true)
    try {
      const res = await fetch(`${API_BASE}/producer/push`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_size: batchSize }),
      })
      const data = await res.json()
      if (data.error) {
        showToast(data.error, 'error')
      } else {
        showToast(`🚀 ${data.message}`, data.n_failures > 0 ? 'error' : 'success')
        fetchStatus()
      }
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setPushing(false)
    }
  }

  const resetSimulation = async () => {
    setResetting(true)
    try {
      await fetch(`${API_BASE}/producer/reset`, { method: 'POST' })
      showToast('Simulation reset successfully!', 'success')
      fetchStatus()
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setResetting(false)
    }
  }

  if (loading) {
    return (
      <div className="spinner-wrap" style={{ paddingTop: 80 }}>
        <span className="spinner" /> Loading Producer...
      </div>
    )
  }

  const pushProgress = status ? (status.pushed_count / status.total) * 100 : 0

  return (
    <>
      <div className="page-header">
        <div className="page-title">
          <h1>🔄 Producer — Simulate Live MES Feed</h1>
        </div>
        <p className="page-caption">
          Simulates the MES + quality inspection APIs. Pushing a batch here is equivalent to a new batch arriving
          live in production. The model has <strong>never seen</strong> these batches.
        </p>
      </div>

      <div className="page-body">
        {/* KPIs */}
        <div className="kpi-grid">
          <div className="kpi-card">
            <span className="kpi-icon">📤</span>
            <div className="kpi-value">{status?.pushed_count ?? 0}</div>
            <div className="kpi-label">Batches Pushed</div>
          </div>
          <div className="kpi-card">
            <span className="kpi-icon">📦</span>
            <div className="kpi-value">{status?.remaining ?? 0}</div>
            <div className="kpi-label">Remaining in Pool</div>
          </div>
          <div className="kpi-card high">
            <span className="kpi-icon">⚠️</span>
            <div className="kpi-value">{status?.n_failures ?? 0}</div>
            <div className="kpi-label">Failures in Pool</div>
          </div>
          <div className="kpi-card">
            <span className="kpi-icon">📊</span>
            <div className="kpi-value">{status?.failure_rate ?? 0}%</div>
            <div className="kpi-label">Failure Rate</div>
          </div>
        </div>

        {/* Pool progress */}
        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">📊 Pool Progress</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
              {status?.pushed_count} / {status?.total}
            </span>
          </div>
          <div className="section-card-body">
            <div className="progress-wrap">
              <div className="progress-fill" style={{ width: `${pushProgress}%` }} />
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 8 }}>
              {pushProgress.toFixed(1)}% of pool consumed
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">🚀 Push Controls</span>
          </div>
          <div className="section-card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="slider-group" style={{ maxWidth: 400 }}>
              <div className="slider-header">
                <span className="slider-label">Batch size to push</span>
                <span className="slider-value">{batchSize}</span>
              </div>
              <input
                type="range" min={1} max={20} step={1}
                value={batchSize}
                onChange={e => setBatchSize(parseInt(e.target.value))}
                id="batch-size-slider"
              />
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <button
                className="btn btn-primary"
                onClick={pushBatch}
                disabled={pushing || (status?.remaining ?? 0) <= 0}
                id="push-batch-btn"
              >
                {pushing ? '⏳ Pushing...' : `🚀 Push Next ${batchSize} Batch${batchSize > 1 ? 'es' : ''}`}
              </button>
              <button
                className="btn btn-danger"
                onClick={resetSimulation}
                disabled={resetting}
                id="reset-sim-btn"
              >
                {resetting ? '⏳ Resetting...' : '🔄 Reset Simulation'}
              </button>
            </div>
            {(status?.remaining ?? 0) <= 0 && (
              <div className="alert-box alert-warning">
                <span>⚠️</span>
                <span>All batches have been pushed! Reset the simulation to start over.</span>
              </div>
            )}
          </div>
        </div>

        {/* Preview table */}
        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">👀 Preview: Next Batches to be Pushed</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Showing next {batchSize} rows with ground truth
            </span>
          </div>
          <div style={{ padding: 0 }}>
            <PreviewTable rows={status?.preview || []} />
          </div>
        </div>

        {/* Failure mode breakdown (expander) */}
        {status?.failure_modes && Object.keys(status.failure_modes).length > 0 && (
          <div className="section-card">
            <button
              className="expander-header"
              onClick={() => setExpandStats(s => !s)}
              style={{ padding: '16px 24px' }}
            >
              <span>📊 Full Pool Statistics</span>
              <span>{expandStats ? '▲' : '▼'}</span>
            </button>
            {expandStats && (
              <div className="section-card-body">
                <div style={{ marginBottom: 8 }}>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginBottom: 4 }}>
                    <strong>Total rows:</strong> {status.total} &nbsp;|&nbsp;
                    <strong>Failure rate:</strong> {status.failure_rate}%
                  </p>
                </div>
                <h4 style={{ marginBottom: 12 }}>Failure Mode Breakdown</h4>
                <MiniBarChart data={status.failure_modes} colorVar="--risk-high" />
                <div style={{ marginTop: 12, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  <strong>Legend:</strong> TWF — Tool Wear · HDF — Heat Dissipation · PWF — Power Failure · OSF — Overstrain · RNF — Random
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
