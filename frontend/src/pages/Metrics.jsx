import { useState, useEffect, useCallback } from 'react'

// ─── Feature Importance Chart ─────────────────────────────────────────────────
function FeatureImportanceChart({ importances }) {
  if (!importances || Object.keys(importances).length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>No feature importance data</p>
  }
  const sorted = Object.entries(importances).sort((a, b) => b[1] - a[1]).slice(0, 10)
  const max = sorted[0][1]
  return (
    <div className="chart-bar-wrap">
      {sorted.map(([feat, imp]) => (
        <div key={feat} className="chart-bar-item">
          <span className="chart-bar-label" title={feat}>{feat.length > 18 ? feat.slice(0, 18) + '…' : feat}</span>
          <div className="chart-bar-track">
            <div className="chart-bar-fill" style={{ width: `${(imp / max) * 100}%` }}>
              <span className="chart-bar-count">{(imp * 100).toFixed(1)}%</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Confusion Matrix ─────────────────────────────────────────────────────────
function ConfusionMatrix({ cm }) {
  if (!cm) return null
  const [[tn, fp], [fn, tp]] = cm
  return (
    <div>
      <div className="confusion-matrix">
        <div className="cm-cell cm-label" />
        <div className="cm-cell cm-label">Pred Normal</div>
        <div className="cm-cell cm-label">Pred Failure</div>
        <div className="cm-cell cm-label">Actual Normal</div>
        <div className={`cm-cell cm-tn`}>{tn}</div>
        <div className={`cm-cell cm-fp`}>{fp}</div>
        <div className="cm-cell cm-label">Actual Failure</div>
        <div className={`cm-cell cm-fn`}>{fn}</div>
        <div className={`cm-cell cm-tp`}>{tp}</div>
      </div>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 12 }}>
        💡 High recall tradeoff is intentional: false alarms are cheaper than missed failures.
      </p>
    </div>
  )
}

// ─── ROI Section ──────────────────────────────────────────────────────────────
function RoiSection({ roi }) {
  if (!roi) {
    return (
      <div className="alert-box alert-info">
        <span>ℹ️</span>
        <span>Run the simulation first to see defect reduction metrics.</span>
      </div>
    )
  }

  const catchRate = roi.total_failures > 0 ? ((roi.caught / roi.total_failures) * 100).toFixed(1) : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <div className="metric-card">
          <div className="metric-value">{roi.caught} / {roi.total_failures}</div>
          <div className="metric-label">Failures Prevented</div>
          <div className="metric-delta positive">↑ {catchRate}% catch rate</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">${(roi.saved_cost / 1000).toFixed(0)}k</div>
          <div className="metric-label">Estimated Cost Saved</div>
          <div className="metric-delta positive">+${roi.saved_cost.toLocaleString()}</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">${(roi.exposed_cost / 1000).toFixed(0)}k</div>
          <div className="metric-label">Residual Risk Exposure</div>
          <div className="metric-delta negative">-${roi.exposed_cost.toLocaleString()}</div>
        </div>
      </div>

      {/* Visual ROI bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
          <span>Failures Caught</span>
          <span>Failures Missed</span>
        </div>
        <div style={{ height: 32, background: 'var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', display: 'flex' }}>
          <div style={{ width: `${catchRate}%`, background: 'linear-gradient(90deg, #10b981, #22d3ee)', display: 'flex', alignItems: 'center', paddingLeft: 12 }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'white' }}>{roi.caught} caught</span>
          </div>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', paddingLeft: 12 }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--risk-high)' }}>{roi.missed} missed</span>
          </div>
        </div>
      </div>

      <div className="alert-box alert-info">
        <span>💡</span>
        <span>
          Based on historical avg repair cost of <strong>${roi.avg_cost.toLocaleString()}</strong>, applying this AI agent
          to the current production queue would save <strong>${roi.saved_cost.toLocaleString()}</strong> by catching{' '}
          <strong>{roi.caught}</strong> defects before they occur.
        </span>
      </div>
    </div>
  )
}

// ─── Feedback Section ─────────────────────────────────────────────────────────
function FeedbackSection({ feedback }) {
  if (!feedback) {
    return (
      <div className="alert-box alert-info">
        <span>ℹ️</span>
        <span>No feedback collected yet. Rate alerts on the Dashboard to see engagement metrics.</span>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <div className="metric-card">
          <div className="metric-value">{feedback.total}</div>
          <div className="metric-label">Total Operator Ratings</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{feedback.helpful_ratio}%</div>
          <div className="metric-label">Helpful Ratio</div>
          <div className="metric-delta positive">👍 {feedback.upvotes} upvotes</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{feedback.corrections}</div>
          <div className="metric-label">Written Corrections</div>
        </div>
      </div>

      {/* Helpfulness bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
          <span>👍 Helpful</span>
          <span>👎 Not helpful</span>
        </div>
        <div style={{ height: 24, background: 'var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden', display: 'flex' }}>
          <div style={{ width: `${feedback.helpful_ratio}%`, background: 'linear-gradient(90deg, #10b981, #22d3ee)' }} />
          <div style={{ flex: 1, background: 'rgba(239,68,68,0.2)' }} />
        </div>
      </div>

      {/* Feedback table */}
      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Batch ID</th>
              <th>Feedback</th>
              <th>Correction</th>
            </tr>
          </thead>
          <tbody>
            {(feedback.records || []).map((r, i) => (
              <tr key={i}>
                <td>{r.batch_id}</td>
                <td>
                  <span className={`badge badge-${r.feedback === 'up' ? 'low' : 'high'}`}>
                    {r.feedback === 'up' ? '👍 Helpful' : '👎 Not helpful'}
                  </span>
                </td>
                <td style={{ maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.correction || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Metrics Page ─────────────────────────────────────────────────────────────
export default function Metrics({ API_BASE, showToast }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics`)
      const json = await res.json()
      setData(json)
    } catch (e) {
      showToast(`Error: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }, [API_BASE, showToast])

  useEffect(() => { fetchData() }, [fetchData])

  if (loading) {
    return <div className="spinner-wrap" style={{ paddingTop: 80 }}><span className="spinner" /> Loading Metrics...</div>
  }

  const model = data?.model
  const roi = data?.roi
  const feedback = data?.feedback

  return (
    <>
      <div className="page-header">
        <div className="page-title"><h1>📈 Success Metrics & ROI</h1></div>
        <p className="page-caption">
          Tracking the three core hackathon success criteria: Prediction Accuracy, Defect Reduction, and User Engagement.
        </p>
      </div>

      <div className="page-body">
        {/* 1. Model Accuracy */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: -8 }}>
          <span style={{ fontSize: '1.2rem' }}>🎯</span>
          <h2>1. Prediction Accuracy</h2>
        </div>

        {!model ? (
          <div className="alert-box alert-info">
            <span>ℹ️</span>
            <span>Metrics not found. Run <code>python train_model.py</code> to generate them.</span>
          </div>
        ) : (
          <>
            {/* Accuracy KPIs */}
            <div className="kpi-grid">
              <div className="kpi-card">
                <span className="kpi-icon">🎯</span>
                <div className="kpi-value">{((model.accuracy || 0) * 100).toFixed(1)}%</div>
                <div className="kpi-label">Model Accuracy</div>
              </div>
              <div className="kpi-card">
                <span className="kpi-icon">🔍</span>
                <div className="kpi-value">{((model.precision || 0) * 100).toFixed(1)}%</div>
                <div className="kpi-label">Precision</div>
              </div>
              <div className="kpi-card high">
                <span className="kpi-icon">🪤</span>
                <div className="kpi-value">{((model.recall || 0) * 100).toFixed(1)}%</div>
                <div className="kpi-label">Recall (Caught)</div>
              </div>
              <div className="kpi-card review">
                <span className="kpi-icon">⚖️</span>
                <div className="kpi-value">{((model.f1 || 0) * 100).toFixed(1)}%</div>
                <div className="kpi-label">F1 Score</div>
              </div>
            </div>

            <div className="analytics-grid-2">
              <div className="section-card">
                <div className="section-card-header">
                  <span className="section-card-title">🗂️ Confusion Matrix (Test Set)</span>
                </div>
                <div className="section-card-body">
                  <ConfusionMatrix cm={model.confusion_matrix} />
                </div>
              </div>
              <div className="section-card">
                <div className="section-card-header">
                  <span className="section-card-title">🌟 Top Predictive Features</span>
                </div>
                <div className="section-card-body">
                  <FeatureImportanceChart importances={model.feature_importance} />
                </div>
              </div>
            </div>
          </>
        )}

        {/* 2. Defect Reduction */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: -8, marginTop: 8 }}>
          <span style={{ fontSize: '1.2rem' }}>🏭</span>
          <h2>2. Defect Reduction & Cost Impact</h2>
        </div>
        <div className="section-card">
          <div className="section-card-body">
            <RoiSection roi={roi} />
          </div>
        </div>

        {/* 3. User Engagement */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: -8 }}>
          <span style={{ fontSize: '1.2rem' }}>💬</span>
          <h2>3. User Engagement & Feedback Loop</h2>
        </div>
        <div className="section-card">
          <div className="section-card-body">
            <FeedbackSection feedback={feedback} />
          </div>
        </div>
      </div>
    </>
  )
}
