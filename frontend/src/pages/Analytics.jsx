import { useState, useEffect, useCallback } from 'react'

// ─── Bar Chart ────────────────────────────────────────────────────────────────
function BarChart({ data, gradient = 'var(--gradient-hero)' }) {
  if (!data || Object.keys(data).length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>No data available</p>
  }
  const max = Math.max(...Object.values(data))
  return (
    <div className="chart-bar-wrap">
      {Object.entries(data)
        .sort((a, b) => b[1] - a[1])
        .map(([label, count]) => (
          <div key={label} className="chart-bar-item">
            <span className="chart-bar-label" title={label}>{label.length > 14 ? label.slice(0, 14) + '…' : label}</span>
            <div className="chart-bar-track">
              <div className="chart-bar-fill" style={{ width: `${(count / max) * 100}%`, background: gradient }}>
                <span className="chart-bar-count">{count}</span>
              </div>
            </div>
          </div>
        ))}
    </div>
  )
}

// ─── Line Sparkline ───────────────────────────────────────────────────────────
function Sparkline({ values = [] }) {
  if (!values.length) return null
  const sample = values.filter((_, i) => i % Math.ceil(values.length / 80) === 0)
  const min = Math.min(...sample)
  const max = Math.max(...sample)
  const range = max - min || 1
  const h = 80
  const w = 600
  const points = sample.map((v, i) => {
    const x = (i / (sample.length - 1)) * w
    const y = h - ((v - min) / range) * h
    return `${x},${y}`
  }).join(' ')

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ height: 80 }}>
      <polyline fill="none" stroke="url(#grad)" strokeWidth="2" points={points} />
      <defs>
        <linearGradient id="grad" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
    </svg>
  )
}

// ─── Data Table ───────────────────────────────────────────────────────────────
function SimpleTable({ rows, cols, formatters = {} }) {
  if (!rows || !rows.length) return <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>No data</p>
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {cols.map(c => (
                <td key={c}>{formatters[c] ? formatters[c](row[c]) : (row[c] ?? '—')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Analytics Page ───────────────────────────────────────────────────────────
export default function Analytics({ API_BASE, showToast }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sensorTab, setSensorTab] = useState(0)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/analytics`)
      const json = await res.json()
      if (json.error) {
        showToast(json.error, 'error')
      }
      setData(json)
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }, [API_BASE, showToast])

  useEffect(() => { fetchData() }, [fetchData])

  if (loading) {
    return <div className="spinner-wrap" style={{ paddingTop: 80 }}><span className="spinner" /> Loading Analytics...</div>
  }

  if (!data || data.error) {
    return (
      <>
        <div className="page-header">
          <div className="page-title"><h1>📊 Quality Analytics</h1></div>
        </div>
        <div className="page-body">
          <div className="alert-box alert-warning">
            <span>⚠️</span>
            <span>{data?.error || 'No data available. Run <code>generate_dataset.py</code> first.'}</span>
          </div>
        </div>
      </>
    )
  }

  const kpis = data.kpis || {}
  const sensorCols = Object.keys(data.sensor_distributions || {})

  return (
    <>
      <div className="page-header">
        <div className="page-title"><h1>📊 Quality Analytics</h1></div>
        <p className="page-caption">
          Historical analysis of defect records, failure modes, and repair costs from the manufacturing production data.
        </p>
      </div>

      <div className="page-body">
        {/* KPIs */}
        <div className="kpi-grid">
          <div className="kpi-card">
            <span className="kpi-icon">🔧</span>
            <div className="kpi-value">{(kpis.total_defects || 0).toLocaleString()}</div>
            <div className="kpi-label">Total Defects</div>
          </div>
          <div className="kpi-card high">
            <span className="kpi-icon">💰</span>
            <div className="kpi-value">${((kpis.total_cost || 0) / 1000).toFixed(0)}k</div>
            <div className="kpi-label">Total Repair Cost</div>
          </div>
          <div className="kpi-card medium">
            <span className="kpi-icon">📊</span>
            <div className="kpi-value">${Math.round(kpis.avg_cost || 0).toLocaleString()}</div>
            <div className="kpi-label">Avg Repair Cost</div>
          </div>
          <div className="kpi-card review">
            <span className="kpi-icon">🚨</span>
            <div className="kpi-value">{(kpis.critical_count || 0).toLocaleString()}</div>
            <div className="kpi-label">Critical Defects</div>
          </div>
        </div>

        {/* Defect Type + Severity */}
        <div className="analytics-grid-2">
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title">🏷️ Defect Type Distribution</span>
            </div>
            <div className="section-card-body">
              <BarChart data={data.defect_types} />
            </div>
          </div>
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title">⚠️ Severity Breakdown</span>
            </div>
            <div className="section-card-body">
              <BarChart
                data={data.severity}
                gradient="linear-gradient(90deg, #ef4444, #f59e0b, #10b981)"
              />
            </div>
          </div>
        </div>

        {/* Failure Mode + Cost by Type */}
        <div className="analytics-grid-2">
          {data.failure_modes && (
            <div className="section-card">
              <div className="section-card-header">
                <span className="section-card-title">🔬 Failure Mode Distribution</span>
              </div>
              <div className="section-card-body">
                <BarChart data={data.failure_modes} gradient="linear-gradient(90deg, #6366f1, #8b5cf6)" />
                <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {[
                    ['TWF', 'Tool Wear Failure'],
                    ['HDF', 'Heat Dissipation Failure'],
                    ['PWF', 'Power Failure'],
                    ['OSF', 'Overstrain Failure'],
                    ['RNF', 'Random Failure'],
                  ].map(([code, desc]) => (
                    <div key={code} style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      <strong style={{ color: 'var(--accent-light)' }}>{code}</strong> — {desc}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title">💰 Repair Cost by Defect Type</span>
            </div>
            <div className="section-card-body" style={{ padding: 0 }}>
              <SimpleTable
                rows={data.cost_by_type || []}
                cols={['defect_type', 'avg_cost', 'total_cost', 'count']}
                formatters={{
                  avg_cost: v => `$${Math.round(v).toLocaleString()}`,
                  total_cost: v => `$${Math.round(v).toLocaleString()}`,
                }}
              />
            </div>
          </div>
        </div>

        {/* Machine-level */}
        {data.machine_defects && (
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title">🏭 Defects by Machine</span>
            </div>
            <div style={{ padding: 0 }}>
              <SimpleTable
                rows={data.machine_defects}
                cols={['machine_id', 'defect_count', 'total_cost', 'critical_count']}
                formatters={{
                  total_cost: v => `$${Math.round(v).toLocaleString()}`,
                }}
              />
            </div>
          </div>
        )}

        {/* Inspection + Locations */}
        <div className="analytics-grid-2">
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title">🔍 Inspection Method Usage</span>
            </div>
            <div className="section-card-body">
              <BarChart data={data.inspection_methods} gradient="linear-gradient(90deg, #22d3ee, #6366f1)" />
            </div>
          </div>
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title">📍 Defect Location Hotspots</span>
            </div>
            <div className="section-card-body">
              <BarChart data={data.defect_locations} gradient="linear-gradient(90deg, #f59e0b, #ef4444)" />
            </div>
          </div>
        </div>

        {/* AI4I2020 overview */}
        {data.ai4i && (
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title">📈 AI4I2020 Training Dataset Overview</span>
            </div>
            <div className="section-card-body">
              <div className="analytics-grid-3" style={{ marginBottom: 20 }}>
                <div className="metric-card">
                  <div className="metric-value">{data.ai4i.total.toLocaleString()}</div>
                  <div className="metric-label">Total Records</div>
                </div>
                <div className="metric-card">
                  <div className="metric-value">{data.ai4i.failure_rate}%</div>
                  <div className="metric-label">Failure Rate</div>
                </div>
                <div className="metric-card">
                  <div className="metric-value">
                    L:{data.ai4i.type_dist?.L || 0} M:{data.ai4i.type_dist?.M || 0} H:{data.ai4i.type_dist?.H || 0}
                  </div>
                  <div className="metric-label">Product Types</div>
                </div>
              </div>

              {sensorCols.length > 0 && (
                <>
                  <h4 style={{ marginBottom: 12 }}>Sensor Reading Distributions (Training Data)</h4>
                  <div className="tabs-bar" style={{ marginBottom: 16 }}>
                    {sensorCols.map((col, i) => (
                      <button
                        key={col}
                        className={`tab-btn ${sensorTab === i ? 'active' : ''}`}
                        onClick={() => setSensorTab(i)}
                      >
                        {col.split(' ')[0]} {col.split(' ')[1] || ''}
                      </button>
                    ))}
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', padding: '12px 0', overflow: 'hidden' }}>
                    <Sparkline values={data.sensor_distributions[sensorCols[sensorTab]] || []} />
                  </div>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 6, textAlign: 'center' }}>
                    {sensorCols[sensorTab]} — first 200 samples
                  </p>
                </>
              )}
            </div>
          </div>
        )}

        {/* Machine Operation Log */}
        {data.dataset && (
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title">⚙️ Machine Operation Log (dataset.csv)</span>
            </div>
            <div className="section-card-body">
              <div className="analytics-grid-3">
                <div className="metric-card">
                  <div className="metric-value">{data.dataset.total_products?.toLocaleString()}</div>
                  <div className="metric-label">Total Products</div>
                </div>
                <div className="metric-card">
                  <div className="metric-value">{data.dataset.quality_pass_rate}%</div>
                  <div className="metric-label">Quality Pass Rate</div>
                </div>
                <div className="metric-card">
                  <div className="metric-value">{Object.keys(data.dataset.status_counts || {}).length}</div>
                  <div className="metric-label">Machine Statuses</div>
                </div>
              </div>
              {Object.keys(data.dataset.status_counts || {}).length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4 style={{ marginBottom: 12 }}>Machine Status Distribution</h4>
                  <BarChart data={data.dataset.status_counts} gradient="linear-gradient(90deg, #10b981, #22d3ee)" />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  )
}
