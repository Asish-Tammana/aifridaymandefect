import { useState, useEffect, useCallback, useRef } from 'react'

// ─── Risk Badge ───────────────────────────────────────────────────────────────
function RiskBadge({ level }) {
  const map = { High: '🔴', Medium: '🟡', Low: '🟢' }
  return (
    <span className={`badge badge-${level?.toLowerCase()}`}>
      {map[level] || '⚪'} {level}
    </span>
  )
}

// ─── KPI Grid ─────────────────────────────────────────────────────────────────
function KpiGrid({ kpis }) {
  return (
    <div className="kpi-grid">
      <div className="kpi-card">
        <span className="kpi-icon">📦</span>
        <div className="kpi-value">{kpis.total}</div>
        <div className="kpi-label">Total Processed</div>
      </div>
      <div className="kpi-card high">
        <span className="kpi-icon">🔴</span>
        <div className="kpi-value">{kpis.high}</div>
        <div className="kpi-label">High Risk</div>
      </div>
      <div className="kpi-card medium">
        <span className="kpi-icon">🟡</span>
        <div className="kpi-value">{kpis.medium}</div>
        <div className="kpi-label">Medium Risk</div>
      </div>
      <div className="kpi-card review">
        <span className="kpi-icon">👁️</span>
        <div className="kpi-value">{kpis.needs_review}</div>
        <div className="kpi-label">Needs Review</div>
      </div>
    </div>
  )
}

// ─── Alerts Table ─────────────────────────────────────────────────────────────
function AlertsTable({ alerts, onSelect, selected }) {
  const [currentPage, setCurrentPage] = useState(1)
  const rowsPerPage = 10
  const compact = ['batch_id', 'timestamp', 'machine_id', 'product_type', 'risk_score', 'risk_level', 'deviated_params']

  if (!alerts.length) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🤖</div>
        <div className="empty-state-title">No batches processed yet</div>
        <p>Push a batch from the <strong>Producer</strong> page to start monitoring.</p>
      </div>
    )
  }

  const totalPages = Math.ceil(alerts.length / rowsPerPage) || 1
  const safePage = Math.min(currentPage, totalPages)
  const startIndex = (safePage - 1) * rowsPerPage
  const currentAlerts = alerts.slice(startIndex, startIndex + rowsPerPage)

  return (
    <div>
      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              {compact.map(col => <th key={col}>{col.replace(/_/g, ' ').toUpperCase()}</th>)}
            </tr>
          </thead>
          <tbody>
            {currentAlerts.map(row => (
              <tr
                key={row.batch_id}
                className={`row-${row.risk_level?.toLowerCase()} ${selected === row.batch_id ? 'selected' : ''}`}
                onClick={() => onSelect(row.batch_id)}
              >
                {compact.map(col => (
                  <td key={col}>
                    {col === 'risk_level' ? <RiskBadge level={row[col]} />
                      : col === 'risk_score' ? (parseFloat(row[col]) || 0).toFixed(3)
                      : col === 'timestamp' ? new Date(row[col]).toLocaleString()
                      : (row[col] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', borderTop: '1px solid var(--border-color)', backgroundColor: 'var(--bg-card)' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Showing {startIndex + 1}-{Math.min(startIndex + rowsPerPage, alerts.length)} of {alerts.length}
          </span>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button 
              className="btn btn-secondary btn-sm" 
              disabled={safePage === 1} 
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <span style={{ fontSize: '0.85rem', margin: '0 8px' }}>
              Page {safePage} of {totalPages}
            </span>
            <button 
              className="btn btn-secondary btn-sm" 
              disabled={safePage === totalPages} 
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Chat Widget ──────────────────────────────────────────────────────────────
function ChatWidget({ batchId, API_BASE }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/dashboard/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_id: batchId, prompt: userMsg }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.response || data.error || 'No response' }])
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', textAlign: 'center', padding: '20px 0' }}>
            Ask the AI about this batch's risk factors, sensor readings, or recommended actions.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className="chat-message">
            <div className={`chat-avatar ${m.role}`}>{m.role === 'user' ? '👤' : '🤖'}</div>
            <div className={`chat-bubble ${m.role}`}>{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="chat-message">
            <div className="chat-avatar assistant">🤖</div>
            <div className="chat-bubble assistant">
              <span className="spinner" style={{ display: 'inline-block', width: 14, height: 14, marginRight: 6 }} />
              Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="chat-input-wrap">
        <input
          className="chat-input"
          type="text"
          placeholder={`Ask a question about batch ${batchId}...`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
        />
        <button className="btn btn-primary btn-sm" onClick={sendMessage} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  )
}

// ─── Drill Down ───────────────────────────────────────────────────────────────
function DrillDown({ batchId, alerts, API_BASE, showToast }) {
  const [correction, setCorrection] = useState('')
  const [showCorrection, setShowCorrection] = useState(false)
  const [retrying, setRetrying] = useState(false)

  const row = alerts.find(a => a.batch_id === batchId)
  if (!row) return null

  const sensorData = [
    { label: 'Air Temp', value: `${row.air_temp_K ?? 'N/A'} K` },
    { label: 'Process Temp', value: `${row.process_temp_K ?? 'N/A'} K` },
    { label: 'RPM', value: row.rpm ?? 'N/A' },
    { label: 'Torque', value: `${row.torque_Nm ?? 'N/A'} Nm` },
    { label: 'Tool Wear', value: `${row.tool_wear_min ?? 'N/A'} min` },
    { label: 'Power', value: `${row.power_W ?? 'N/A'} W` },
    { label: 'Temp Diff', value: `${row.temp_diff ?? 'N/A'} K` },
  ]

  const submitFeedback = async (feedback) => {
    try {
      await fetch(`${API_BASE}/dashboard/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_id: batchId, feedback, correction }),
      })
      showToast('Thanks for the feedback! 🎉', 'success')
      setShowCorrection(false)
      setCorrection('')
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error')
    }
  }

  const retryAnalysis = async () => {
    setRetrying(true)
    try {
      const res = await fetch(`${API_BASE}/dashboard/retry/${batchId}`, { method: 'POST' })
      const data = await res.json()
      if (data.success) showToast('AI analysis retried successfully!', 'success')
      else showToast(`Retry failed: ${data.error}`, 'error')
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setRetrying(false)
    }
  }

  const isFailed = row.probable_cause?.startsWith('Reasoning call failed')

  return (
    <div className="drill-grid">
      {/* Left: Risk Assessment */}
      <div>
        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">🔍 Risk Assessment — {batchId}</span>
            <RiskBadge level={row.risk_level} />
          </div>
          <div className="section-card-body">
            <div className="info-row">
              <span className="info-label">Risk Score</span>
              <span className="info-value" style={{ fontFamily: 'JetBrains Mono', fontSize: '1.1rem', color: row.risk_level === 'High' ? 'var(--risk-high)' : row.risk_level === 'Medium' ? 'var(--risk-medium)' : 'var(--risk-low)' }}>
                {parseFloat(row.risk_score || 0).toFixed(3)}
              </span>
            </div>
            <div className="info-row">
              <span className="info-label">Product Type</span>
              <span className="info-value">{row.product_type || 'N/A'}</span>
            </div>
            <div className="info-row">
              <span className="info-label">Machine ID</span>
              <span className="info-value">{row.machine_id || 'N/A'}</span>
            </div>
            <div className="info-row">
              <span className="info-label">Deviated Parameters</span>
              <span className="info-value" style={{ color: 'var(--risk-medium)' }}>{row.deviated_params || 'None'}</span>
            </div>
            <div className="info-row">
              <span className="info-label">Confidence</span>
              <span className="info-value">{row.confidence || 'N/A'}</span>
            </div>

            {isFailed ? (
              <div style={{ marginTop: 12 }}>
                <div className="alert-box alert-error">
                  <span>⚠️</span>
                  <span>{row.probable_cause}</span>
                </div>
                <button className="btn btn-secondary btn-sm" style={{ marginTop: 10 }} onClick={retryAnalysis} disabled={retrying}>
                  {retrying ? '⏳ Retrying...' : '🔄 Retry AI Analysis'}
                </button>
              </div>
            ) : (
              <div style={{ marginTop: 12 }}>
                {row.probable_cause && (
                  <div className="alert-box alert-info" style={{ marginBottom: 8 }}>
                    <span>🤖</span>
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>Probable Cause</div>
                      <div style={{ fontSize: '0.82rem' }}>{row.probable_cause}</div>
                    </div>
                  </div>
                )}
                {row.recommended_action && (
                  <div className="alert-box alert-success">
                    <span>🔧</span>
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>Recommended Action</div>
                      <div style={{ fontSize: '0.82rem' }}>{row.recommended_action}</div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {row.needs_human_review && (
              <div className="alert-box alert-warning" style={{ marginTop: 10 }}>
                <span>⚠️</span>
                <span>Flagged for human review by the output guardrail.</span>
              </div>
            )}
          </div>
        </div>

        {/* Chat */}
        <div className="section-card" style={{ marginTop: 16 }}>
          <div className="section-card-header">
            <span className="section-card-title">💬 AI Assistant</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Ask follow-up questions</span>
          </div>
          <div className="section-card-body">
            <ChatWidget batchId={batchId} API_BASE={API_BASE} />
          </div>
        </div>
      </div>

      {/* Right: Sensors + Feedback */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">📡 Sensor Readings</span>
          </div>
          <div className="section-card-body">
            <div className="sensor-grid">
              {sensorData.map(s => (
                <div key={s.label} className="sensor-item">
                  <div className="sensor-label">{s.label}</div>
                  <div className="sensor-value">{s.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">💬 Operator Feedback</span>
          </div>
          <div className="section-card-body">
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 12 }}>Was this alert helpful?</p>
            <div className="feedback-group">
              <button className="btn btn-secondary btn-sm" onClick={() => submitFeedback('up')}>👍 Helpful</button>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowCorrection(s => !s)}>👎 Not helpful</button>
            </div>
            {showCorrection && (
              <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <input
                  className="chat-input"
                  type="text"
                  placeholder="What was the actual issue?"
                  value={correction}
                  onChange={e => setCorrection(e.target.value)}
                />
                <button className="btn btn-secondary btn-sm" onClick={() => submitFeedback('down')}>Submit Correction</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Dashboard Page ───────────────────────────────────────────────────────────
export default function Dashboard({ API_BASE, showToast, autoRefresh, refreshSeconds }) {
  const [data, setData] = useState({ alerts: [], kpis: { total: 0, high: 0, medium: 0, needs_review: 0 } })
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [selectedBatch, setSelectedBatch] = useState(null)

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/alerts`)
      const json = await res.json()
      setData(json)
    } catch (e) {
      console.error('Failed to fetch alerts:', e)
    } finally {
      setLoading(false)
    }
  }, [API_BASE])

  const processNewBatches = useCallback(async () => {
    setProcessing(true)
    try {
      const res = await fetch(`${API_BASE}/dashboard/process`, { method: 'POST' })
      const json = await res.json()
      if (json.error) {
        showToast(`Processing error: ${json.error}`, 'error')
      } else if (json.processed > 0) {
        showToast(`✅ Processed ${json.processed} new batch(es)`, 'success')
        fetchAlerts()
      }
    } catch (e) {
      console.error('Process error:', e)
    } finally {
      setProcessing(false)
    }
  }, [API_BASE, showToast, fetchAlerts])

  useEffect(() => {
    fetchAlerts()
    processNewBatches()
  }, [fetchAlerts, processNewBatches])

  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => {
      processNewBatches()
      fetchAlerts()
    }, refreshSeconds * 1000)
    return () => clearInterval(id)
  }, [autoRefresh, refreshSeconds, processNewBatches, fetchAlerts])

  const riskyAlerts = data.alerts.filter(a => ['High', 'Medium'].includes(a.risk_level))

  return (
    <>
      <div className="page-header">
        <div className="page-title">
          <h1>🏭 Live Defect Risk Dashboard</h1>
          {processing && <span className="spinner" />}
        </div>
        <p className="page-caption">
          Reads new batches pushed from the Producer page, scores them with the ML model (Random Forest on AI4I2020 features),
          and calls the LLM for an explanation when risk is high.
        </p>
      </div>

      <div className="page-body">
        {loading ? (
          <div className="spinner-wrap"><span className="spinner" /> Loading dashboard...</div>
        ) : (
          <>
            <KpiGrid kpis={data.kpis} />

            <div className="section-card">
              <div className="section-card-header">
                <span className="section-card-title">📋 Batch Risk Table</span>
                <button className="btn btn-secondary btn-sm" onClick={() => { processNewBatches(); fetchAlerts() }}>
                  🔄 Refresh
                </button>
              </div>
              <div className="section-card-body" style={{ padding: 0 }}>
                <AlertsTable alerts={data.alerts} onSelect={setSelectedBatch} selected={selectedBatch} />
              </div>
            </div>

            <div className="section-card">
              <div className="section-card-header">
                <span className="section-card-title">🔍 Batch Drill-Down</span>
              </div>
              <div className="section-card-body">
                {riskyAlerts.length === 0 ? (
                  <div className="alert-box alert-success">
                    <span>✅</span>
                    <span>No risky batches detected yet! All processed batches are Low risk.</span>
                  </div>
                ) : (
                  <>
                    <div style={{ marginBottom: 16 }}>
                      <div className="select-wrap" style={{ maxWidth: 320 }}>
                        <select
                          value={selectedBatch || ''}
                          onChange={e => setSelectedBatch(e.target.value)}
                          id="batch-select"
                        >
                          <option value="">Select a risky batch to investigate</option>
                          {riskyAlerts.map(a => (
                            <option key={a.batch_id} value={a.batch_id}>
                              {a.batch_id} — {a.risk_level} ({parseFloat(a.risk_score || 0).toFixed(3)})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    {selectedBatch && (
                      <DrillDown
                        batchId={selectedBatch}
                        alerts={data.alerts}
                        API_BASE={API_BASE}
                        showToast={showToast}
                      />
                    )}
                  </>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  )
}
