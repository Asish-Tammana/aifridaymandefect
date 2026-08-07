import { useState } from 'react'

export default function Auth({ API_BASE, onLogin, showToast }) {
  const [isLogin, setIsLogin] = useState(true)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('USER')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username || !password) {
      showToast('Username and password are required', 'error')
      return
    }

    setLoading(true)
    const endpoint = isLogin ? '/login' : '/signup'
    const payload = isLogin ? { username, password } : { username, password, role }

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()

      if (res.ok && data.success) {
        if (isLogin) {
          showToast(`Welcome back, ${data.user.username}!`, 'success')
          onLogin(data.user)
        } else {
          showToast('Signup successful! You can now log in.', 'success')
          setIsLogin(true)
          setPassword('')
        }
      } else {
        showToast(data.error || 'An error occurred', 'error')
      }
    } catch (err) {
      showToast(`Network error: ${err.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', width: '100vw', backgroundColor: 'var(--bg-color)' }}>
      <div className="section-card" style={{ width: 400, padding: 30 }}>
        <h2 style={{ textAlign: 'center', marginBottom: 20 }}>
          {isLogin ? 'Welcome Back' : 'Create Account'}
        </h2>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: '0.85rem' }}>Username</label>
            <input
              type="text"
              className="chat-input"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="Enter username"
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: '0.85rem' }}>Password</label>
            <input
              type="password"
              className="chat-input"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter password"
              style={{ width: '100%' }}
            />
          </div>
          {!isLogin && (
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.85rem' }}>Role</label>
              <select 
                className="chat-input" 
                value={role} 
                onChange={e => setRole(e.target.value)}
                style={{ width: '100%', cursor: 'pointer' }}
              >
                <option value="USER">USER</option>
                <option value="ADMIN">ADMIN</option>
              </select>
            </div>
          )}
          <button type="submit" className="btn btn-primary" style={{ marginTop: 10 }} disabled={loading}>
            {loading ? 'Processing...' : isLogin ? 'Log In' : 'Sign Up'}
          </button>
        </form>
        <div style={{ textAlign: 'center', marginTop: 20, fontSize: '0.85rem' }}>
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <button 
            className="btn btn-ghost btn-sm" 
            onClick={() => setIsLogin(!isLogin)}
            style={{ padding: '2px 8px' }}
          >
            {isLogin ? 'Sign Up' : 'Log In'}
          </button>
        </div>
      </div>
    </div>
  )
}
