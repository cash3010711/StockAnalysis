import React from 'react'
import { ApiError } from '../types/api'

interface AlertBannerProps {
  error?: Error | ApiError | null
  warnings?: string[]
}

export const AlertBanner: React.FC<AlertBannerProps> = ({ error, warnings = [] }) => {
  if (!error && warnings.length === 0) {
    return null
  }

  const isApiError = error instanceof ApiError
  const errorCode = isApiError ? error.code : null
  const isTokenMissing = errorCode === 'TOKEN_MISSING'

  return (
    <div style={{ margin: '16px 0', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {error && (
        <div
          data-testid="error-banner"
          style={{
            padding: '16px',
            background: '#fef2f2',
            border: '1px solid #f87171',
            borderRadius: '8px',
            color: '#991b1b',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold' }}>
            <span style={{ fontSize: '18px' }}>⚠️</span>
            <span>{error.message}</span>
          </div>

          {isApiError && error.hint && (
            <p style={{ margin: '8px 0 0 0', fontSize: '14px', color: '#b91c1c' }}>
              提示：{error.hint}
            </p>
          )}

          {isTokenMissing && (
            <div
              data-testid="token-missing-steps"
              style={{
                marginTop: '12px',
                padding: '12px',
                background: '#ffffff',
                border: '1px solid #fca5a5',
                borderRadius: '6px',
                fontSize: '13px',
                color: '#334155',
              }}
            >
              <p style={{ margin: '0 0 8px 0', fontWeight: 'bold', color: '#0f172a' }}>
                FinMind API Token 設定步驟：
              </p>
              <ol style={{ margin: 0, paddingLeft: '20px', lineHeight: '1.6' }}>
                <li>
                  前往{' '}
                  <a
                    href="https://finmindtrade.com"
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: '#2563eb', textDecoration: 'underline' }}
                  >
                    FinMind 官網
                  </a>{' '}
                  註冊並登入會員以取得個人免費 API Token。
                </li>
                <li>
                  在專案的 <code>backend/.env</code> 檔案中填入：
                  <pre
                    style={{
                      background: '#f1f5f9',
                      padding: '6px 10px',
                      borderRadius: '4px',
                      margin: '6px 0',
                    }}
                  >
                    FINMIND_TOKEN=你的FinMindToken
                  </pre>
                </li>
                <li>重新啟動後端服務，或參考專案根目錄的 <code>README.md</code> 完整說明。</li>
              </ol>
            </div>
          )}
        </div>
      )}

      {warnings.length > 0 && (
        <div
          data-testid="warning-banner"
          style={{
            padding: '12px 16px',
            background: '#fffbeb',
            border: '1px solid #fcd34d',
            borderRadius: '8px',
            color: '#92400e',
            fontSize: '14px',
          }}
        >
          <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>資料警示：</div>
          <ul style={{ margin: 0, paddingLeft: '20px' }}>
            {warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
