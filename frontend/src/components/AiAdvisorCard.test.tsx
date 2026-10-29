import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as clientModule from '../api/client'
import { AiAdvisorCard } from './AiAdvisorCard'
import { ApiError } from '../types/api'

describe('AiAdvisorCard Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders initial idle state with generate button', () => {
    render(
      <AiAdvisorCard
        stockId="2330"
        stockName="台積電"
        evaluationDate="2026-10-29"
      />
    )

    expect(screen.getByText('AI 盤後戰略解讀')).toBeInTheDocument()
    expect(screen.getByTestId('generate-ai-advice-btn')).toBeInTheDocument()
    expect(screen.getByTestId('ai-advisor-idle')).toBeInTheDocument()
  })

  it('handles streaming generation and renders formatted content', async () => {
    const streamSpy = vi.spyOn(clientModule, 'streamAiAdvice').mockImplementation(
      async (_stockId, options) => {
        // First chunk
        options?.onChunk?.('### 1. 【進場適宜度判定】\n', '### 1. 【進場適宜度判定】\n')
        // Second chunk
        options?.onChunk?.('目前均線呈多頭排列。\n', '### 1. 【進場適宜度判定】\n目前均線呈多頭排列。\n')
        options?.onEvent?.({ done: true })
        return '### 1. 【進場適宜度判定】\n目前均線呈多頭排列。\n'
      }
    )

    render(
      <AiAdvisorCard
        stockId="2330"
        stockName="台積電"
        evaluationDate="2026-10-29"
      />
    )

    const generateBtn = screen.getByTestId('generate-ai-advice-btn')
    await act(async () => {
      fireEvent.click(generateBtn)
    })

    expect(streamSpy).toHaveBeenCalledWith('2330', expect.objectContaining({ force: false }))
    expect(screen.getByTestId('ai-advice-content')).toBeInTheDocument()
    expect(screen.getByText('1. 【進場適宜度判定】')).toBeInTheDocument()
    expect(screen.getByText('目前均線呈多頭排列。')).toBeInTheDocument()
    expect(screen.getByTestId('regenerate-ai-advice-btn')).toBeInTheDocument()
  })

  it('displays cached badge when loaded from local cache', async () => {
    vi.spyOn(clientModule, 'streamAiAdvice').mockImplementation(
      async (_stockId, options) => {
        const cachedContent = '### 1. 【進場適宜度判定】\n快取戰略內容'
        options?.onChunk?.(cachedContent, cachedContent)
        options?.onEvent?.({ cached: true, done: true, text: cachedContent })
        return cachedContent
      }
    )

    render(
      <AiAdvisorCard
        stockId="2330"
        stockName="台積電"
        evaluationDate="2026-10-29"
      />
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('generate-ai-advice-btn'))
    })

    expect(screen.getByTestId('ai-cached-badge')).toHaveTextContent('本機當日快取')
  })

  it('calls stream with force=true when regenerate button is clicked', async () => {
    const streamSpy = vi.spyOn(clientModule, 'streamAiAdvice').mockImplementation(
      async (_stockId, options) => {
        options?.onChunk?.('內容', '內容')
        options?.onEvent?.({ done: true })
        return '內容'
      }
    )

    render(
      <AiAdvisorCard
        stockId="2330"
        stockName="台積電"
        evaluationDate="2026-10-29"
      />
    )

    // Initial generate
    await act(async () => {
      fireEvent.click(screen.getByTestId('generate-ai-advice-btn'))
    })

    // Click regenerate
    const regenBtn = screen.getByTestId('regenerate-ai-advice-btn')
    await act(async () => {
      fireEvent.click(regenBtn)
    })

    expect(streamSpy).toHaveBeenLastCalledWith('2330', expect.objectContaining({ force: true }))
  })

  it('displays friendly API key missing guidance when GEMINI_API_KEY is not configured', async () => {
    vi.spyOn(clientModule, 'streamAiAdvice').mockRejectedValue(
      new ApiError(400, {
        code: 'GEMINI_API_KEY_MISSING',
        message: '尚未設定 Gemini API 金鑰',
      })
    )

    render(
      <AiAdvisorCard
        stockId="2330"
        stockName="台積電"
        evaluationDate="2026-10-29"
      />
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('generate-ai-advice-btn'))
    })

    expect(screen.getByTestId('api-key-missing-alert')).toBeInTheDocument()
    expect(screen.getByText('尚未設定 Google Gemini API 金鑰')).toBeInTheDocument()
    expect(screen.getByText(/GEMINI_API_KEY=your_gemini_api_key_here/)).toBeInTheDocument()
    expect(screen.getByTestId('retry-after-key-btn')).toBeInTheDocument()
  })

  it('resets state when stockId changes', async () => {
    vi.spyOn(clientModule, 'streamAiAdvice').mockImplementation(
      async (_stockId, options) => {
        options?.onChunk?.('2330內容', '2330內容')
        options?.onEvent?.({ done: true })
        return '2330內容'
      }
    )

    const { rerender } = render(
      <AiAdvisorCard
        stockId="2330"
        stockName="台積電"
        evaluationDate="2026-10-29"
      />
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('generate-ai-advice-btn'))
    })
    expect(screen.getByText('2330內容')).toBeInTheDocument()

    // Switch stock to 2317
    rerender(
      <AiAdvisorCard
        stockId="2317"
        stockName="鴻海"
        evaluationDate="2026-10-29"
      />
    )

    // Should be back to idle state with generate button
    expect(screen.getByTestId('ai-advisor-idle')).toBeInTheDocument()
    expect(screen.queryByText('2330內容')).not.toBeInTheDocument()
  })
})
