import React, { useEffect, useRef, useState } from 'react'
import { streamAiAdvice } from '../api/client'
import { ApiError } from '../types/api'

interface AiAdvisorCardProps {
  stockId: string
  stockName: string
  evaluationDate: string
}

type CardStatus = 'idle' | 'loading' | 'streaming' | 'success' | 'error'

/**
 * Lightweight safe markdown renderer for AI advisor output.
 */
function renderMarkdown(content: string) {
  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let listItems: string[] = []

  const flushList = (keyPrefix: string) => {
    if (listItems.length > 0) {
      elements.push(
        <ul
          key={`${keyPrefix}-list`}
          style={{
            margin: '6px 0 12px 20px',
            paddingLeft: '0',
            lineHeight: '1.7',
            color: '#334155',
          }}
        >
          {listItems.map((item, idx) => (
            <li key={idx} dangerouslySetInnerHTML={{ __html: formatInline(item) }} />
          ))}
        </ul>
      )
      listItems = []
    }
  }

  const formatInline = (text: string) => {
    // Replace **bold** with <strong>
    return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  }

  lines.forEach((line, index) => {
    const trimmed = line.trim()

    if (trimmed.startsWith('### ')) {
      flushList(`flush-${index}`)
      elements.push(
        <h4
          key={`h4-${index}`}
          style={{
            margin: '18px 0 8px 0',
            fontSize: '16px',
            fontWeight: 700,
            color: '#0f172a',
            borderLeft: '4px solid #2563eb',
            paddingLeft: '10px',
          }}
        >
          {trimmed.replace(/^###\s+/, '')}
        </h4>
      )
    } else if (trimmed.startsWith('## ')) {
      flushList(`flush-${index}`)
      elements.push(
        <h3
          key={`h3-${index}`}
          style={{
            margin: '20px 0 10px 0',
            fontSize: '18px',
            fontWeight: 700,
            color: '#0f172a',
          }}
        >
          {trimmed.replace(/^##\s+/, '')}
        </h3>
      )
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      listItems.push(trimmed.substring(2))
    } else if (trimmed === '') {
      flushList(`flush-${index}`)
    } else {
      flushList(`flush-${index}`)
      elements.push(
        <p
          key={`p-${index}`}
          style={{
            margin: '6px 0 10px 0',
            lineHeight: '1.7',
            color: '#334155',
            fontSize: '14px',
          }}
          dangerouslySetInnerHTML={{ __html: formatInline(trimmed) }}
        />
      )
    }
  })

  flushList('final')
  return elements
}

export const AiAdvisorCard: React.FC<AiAdvisorCardProps> = ({
  stockId,
  stockName,
  evaluationDate,
}) => {
  const [content, setContent] = useState<string>('')
  const [status, setStatus] = useState<CardStatus>('idle')
  const [isCached, setIsCached] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isApiKeyMissing, setIsApiKeyMissing] = useState<boolean>(false)
  const [copied, setCopied] = useState<boolean>(false)

  const abortControllerRef = useRef<AbortController | null>(null)

  // Reset when stockId changes
  useEffect(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setContent('')
    setStatus('idle')
    setIsCached(false)
    setErrorMessage(null)
    setIsApiKeyMissing(false)
    setCopied(false)
  }, [stockId])

  const handleGenerate = async (force: boolean = false) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const ac = new AbortController()
    abortControllerRef.current = ac

    setStatus('loading')
    setErrorMessage(null)
    setIsApiKeyMissing(false)
    setContent('')
    setIsCached(false)

    try {
      await streamAiAdvice(stockId, {
        force,
        signal: ac.signal,
        onChunk: (_delta, accumulated) => {
          setStatus('streaming')
          setContent(accumulated)
        },
        onEvent: (event) => {
          if (event.cached) {
            setIsCached(true)
          }
          if (event.done) {
            setStatus('success')
          }
        },
      })
      setStatus('success')
    } catch (err: unknown) {
      if ((err as Error)?.name === 'AbortError' || ac.signal.aborted) {
        return
      }

      setStatus('error')
      if (err instanceof ApiError) {
        if (err.code === 'GEMINI_API_KEY_MISSING') {
          setIsApiKeyMissing(true)
          setErrorMessage(err.message || '尚未設定 Gemini API 金鑰')
        } else {
          setErrorMessage(err.message || `請求失敗 (HTTP ${err.status})`)
        }
      } else {
        setErrorMessage((err as Error).message || 'AI 戰略分析生成失敗')
      }
    } finally {
      if (abortControllerRef.current === ac) {
        abortControllerRef.current = null
      }
    }
  }

  const handleCopy = () => {
    if (!content) return
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const isGenerating = status === 'loading' || status === 'streaming'

  return (
    <div
      data-testid="ai-advisor-card"
      style={{
        marginTop: '20px',
        padding: '20px',
        borderRadius: '10px',
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        boxShadow: '0 2px 4px rgba(0, 0, 0, 0.04)',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '10px',
          paddingBottom: '12px',
          borderBottom: '1px solid #f1f5f9',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <h3
            style={{
              margin: 0,
              fontSize: '18px',
              fontWeight: 700,
              color: '#0f172a',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>🤖</span>
            <span>AI 盤後戰略解讀</span>
          </h3>

          <span style={{ fontSize: '13px', color: '#64748b' }}>
            ({stockName} · {evaluationDate})
          </span>

          {isCached && status === 'success' && (
            <span
              data-testid="ai-cached-badge"
              style={{
                fontSize: '12px',
                padding: '2px 8px',
                borderRadius: '12px',
                backgroundColor: '#e0f2fe',
                color: '#0369a1',
                fontWeight: 600,
              }}
            >
              本機當日快取
            </span>
          )}

          {isGenerating && (
            <span
              data-testid="ai-generating-badge"
              style={{
                fontSize: '12px',
                padding: '2px 8px',
                borderRadius: '12px',
                backgroundColor: '#fef3c7',
                color: '#b45309',
                fontWeight: 600,
              }}
            >
              即時解讀生成中...
            </span>
          )}
        </div>

        {/* Action Controls for generated state */}
        {content && !isGenerating && (
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              data-testid="copy-ai-advice-btn"
              onClick={handleCopy}
              style={{
                padding: '5px 12px',
                fontSize: '13px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                color: '#475569',
                cursor: 'pointer',
                fontWeight: 500,
              }}
            >
              {copied ? '✓ 已複製' : '📋 複製'}
            </button>
            <button
              type="button"
              data-testid="regenerate-ai-advice-btn"
              onClick={() => handleGenerate(true)}
              disabled={isGenerating}
              style={{
                padding: '5px 12px',
                fontSize: '13px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                color: '#2563eb',
                cursor: isGenerating ? 'not-allowed' : 'pointer',
                fontWeight: 600,
              }}
            >
              🔄 重新解讀
            </button>
          </div>
        )}
      </div>

      {/* API Key Missing Alert */}
      {isApiKeyMissing && (
        <div
          data-testid="api-key-missing-alert"
          style={{
            padding: '16px',
            backgroundColor: '#fffbeb',
            border: '1px solid #fde68a',
            borderRadius: '8px',
            marginBottom: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <span style={{ fontSize: '18px' }}>⚠️</span>
            <strong style={{ color: '#92400e', fontSize: '15px' }}>
              尚未設定 Google Gemini API 金鑰
            </strong>
          </div>
          <p style={{ margin: '0 0 10px 0', fontSize: '13px', color: '#78350f', lineHeight: '1.6' }}>
            AI 盤後戰略解讀需搭配 Google Gemini API。請至{' '}
            <a
              href="https://aistudio.google.com/"
              target="_blank"
              rel="noreferrer"
              style={{ color: '#2563eb', textDecoration: 'underline' }}
            >
              Google AI Studio
            </a>{' '}
            免費申請 API 金鑰，並在後端 <code>backend/.env</code> 檔案中配置：
          </p>
          <pre
            style={{
              background: '#fef3c7',
              padding: '8px 12px',
              borderRadius: '6px',
              fontSize: '13px',
              fontFamily: 'monospace',
              color: '#451a03',
              margin: '0 0 12px 0',
            }}
          >
            GEMINI_API_KEY=your_gemini_api_key_here
          </pre>
          <button
            type="button"
            data-testid="retry-after-key-btn"
            onClick={() => handleGenerate(false)}
            style={{
              padding: '6px 14px',
              fontSize: '13px',
              borderRadius: '6px',
              border: 'none',
              background: '#d97706',
              color: '#ffffff',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            已設定，重試分析
          </button>
        </div>
      )}

      {/* General Error Alert */}
      {status === 'error' && !isApiKeyMissing && (
        <div
          data-testid="ai-error-alert"
          style={{
            padding: '14px 16px',
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '8px',
            marginBottom: '16px',
            color: '#b91c1c',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <strong>生成失敗：</strong>
            <span>{errorMessage || '未知錯誤，請稍後重試'}</span>
          </div>
          <button
            type="button"
            onClick={() => handleGenerate(false)}
            style={{
              padding: '4px 10px',
              fontSize: '13px',
              borderRadius: '6px',
              border: '1px solid #fca5a5',
              background: '#ffffff',
              color: '#b91c1c',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            重試
          </button>
        </div>
      )}

      {/* Idle Initial State */}
      {status === 'idle' && (
        <div
          data-testid="ai-advisor-idle"
          style={{
            padding: '30px 20px',
            textAlign: 'center',
            backgroundColor: '#f8fafc',
            borderRadius: '8px',
            border: '1px dashed #cbd5e1',
          }}
        >
          <p
            style={{
              margin: '0 0 16px 0',
              fontSize: '14px',
              color: '#64748b',
              lineHeight: '1.6',
            }}
          >
            由 Google Gemini 戰略顧問綜合本標的最新技術均線、三層濾網與多因子起漲評分，即時輸出個人化波段進出場規劃與風險警訊。
          </p>
          <button
            type="button"
            data-testid="generate-ai-advice-btn"
            onClick={() => handleGenerate(false)}
            style={{
              padding: '10px 24px',
              fontSize: '15px',
              fontWeight: 600,
              borderRadius: '8px',
              border: 'none',
              background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
              color: '#ffffff',
              cursor: 'pointer',
              boxShadow: '0 2px 6px rgba(37, 99, 235, 0.3)',
              transition: 'transform 0.1s ease',
            }}
          >
            ✨ 一鍵生成戰略分析
          </button>
        </div>
      )}

      {/* Loading (before any token) */}
      {status === 'loading' && !content && (
        <div
          data-testid="ai-advisor-loading"
          style={{
            padding: '30px 20px',
            textAlign: 'center',
            color: '#64748b',
            fontSize: '14px',
          }}
        >
          <div style={{ marginBottom: '8px', fontSize: '20px' }}>⏳</div>
          <div>正在分析量化指標並連接 Gemini AI 戰略模型...</div>
        </div>
      )}

      {/* Streaming or Success Content Area */}
      {content && (
        <div
          data-testid="ai-advice-content"
          style={{
            backgroundColor: '#f8fafc',
            borderRadius: '8px',
            padding: '16px 20px',
            border: '1px solid #e2e8f0',
            fontSize: '14px',
            lineHeight: '1.7',
          }}
        >
          {renderMarkdown(content)}
          {status === 'streaming' && (
            <span
              data-testid="ai-typewriter-cursor"
              style={{
                display: 'inline-block',
                width: '8px',
                height: '16px',
                backgroundColor: '#2563eb',
                marginLeft: '4px',
                verticalAlign: 'middle',
                animation: 'pulse 1s infinite',
              }}
            />
          )}
        </div>
      )}
    </div>
  )
}
