import { useEffect, useState } from 'react'
import './App.css'

interface HealthResponse {
  status: string
  finmind_token_configured: boolean
}

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`)
        }
        return res.json()
      })
      .then((data: HealthResponse) => {
        setHealth(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return (
    <div style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif', maxWidth: '800px', margin: '0 auto' }}>
      <h1>台股波段策略分析儀</h1>
      <p style={{ color: '#666' }}>Taiwan Stock Swing Strategy Analyzer</p>

      <div style={{ marginTop: '2rem', padding: '1.5rem', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#f8fafc' }}>
        <h2>後端健康檢查 (/api/health)</h2>
        {loading && <p>正在連線後端 API (/api/health)...</p>}
        {error && (
          <div style={{ color: '#dc2626' }}>
            <p>連線失敗：{error}</p>
            <p style={{ fontSize: '0.9rem', color: '#666' }}>請確認後端是否已在 localhost:8000 啟動 (<code>uv run uvicorn app.main:app</code>)</p>
          </div>
        )}
        {health && (
          <div style={{ color: '#16a34a' }}>
            <p><strong>連線狀態：</strong> {health.status === 'ok' ? '正常 (200 OK)' : health.status}</p>
            <p><strong>FinMind Token 設定：</strong> {health.finmind_token_configured ? '已設定' : '未設定 (請於 backend/.env 設定 FINMIND_TOKEN)'}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
