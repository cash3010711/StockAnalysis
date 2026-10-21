import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AlertBanner } from './AlertBanner'
import { Disclaimer } from './Disclaimer'
import { EvaluationHeader } from './EvaluationHeader'
import { LayersSummary } from './LayersSummary'
import { ApiError } from '../types/api'

describe('EvaluationHeader & Disclaimer', () => {
  it('renders evaluation date with "（收盤後資料）" and disclaimer', () => {
    render(
      <>
        <EvaluationHeader
          stockId="2330"
          stockName="台積電"
          evaluationDate="2026-10-21"
        />
        <Disclaimer />
      </>
    )

    expect(screen.getByText('2330 台積電')).toBeInTheDocument()
    expect(screen.getByTestId('eval-date-text')).toHaveTextContent(
      '評估日：2026-10-21（收盤後資料）'
    )
    expect(
      screen.getByText(/僅供個人研究參考，非投資建議/)
    ).toBeInTheDocument()
  })
})

describe('LayersSummary', () => {
  it('renders passed fundamentals and failed chips with reasons and values', () => {
    const fundamental = {
      passed: true,
      revenue_yoy: 0.152,
      eps_4q_sum: 35.8,
      debt_ratio: 0.32,
      reason: '',
    }
    const chips = {
      passed: false,
      foreign_trust_net_buy_10d: -3200,
      margin_increase_rate_10d: 0.05,
      reason: '外資＋投信近 10 日賣超 3,200 張',
    }

    render(<LayersSummary fundamental={fundamental} chips={chips} />)

    // Fundamental passed
    const fundamentalCard = screen.getByTestId('fundamental-card')
    expect(fundamentalCard).toHaveTextContent('✓ 通過')
    expect(fundamentalCard).toHaveTextContent('15.20%')
    expect(fundamentalCard).toHaveTextContent('35.80 元')
    expect(fundamentalCard).toHaveTextContent('32.00%')

    // Chips failed
    const chipsCard = screen.getByTestId('chips-card')
    expect(chipsCard).toHaveTextContent('✗ 未通過')
    expect(chipsCard).toHaveTextContent('賣超 3,200 張')
    expect(screen.getByTestId('chips-reason')).toHaveTextContent(
      '外資＋投信近 10 日賣超 3,200 張'
    )
  })
})

describe('AlertBanner', () => {
  it('renders TOKEN_MISSING error with token setup instructions', () => {
    const error = new ApiError(401, {
      code: 'TOKEN_MISSING',
      message: '尚未設定 FinMind API Token',
      hint: '請至 FinMind 官網免費申請',
    })

    render(<AlertBanner error={error} />)

    expect(screen.getByTestId('error-banner')).toHaveTextContent(
      '尚未設定 FinMind API Token'
    )
    expect(screen.getByTestId('token-missing-steps')).toBeInTheDocument()
    expect(screen.getByText(/backend\/\.env/)).toBeInTheDocument()
  })

  it('renders warnings list when warnings provided', () => {
    render(
      <AlertBanner
        warnings={['API 額度已用盡，改由快取提供', '歷史日 K 不足 5 年']}
      />
    )

    const warningBanner = screen.getByTestId('warning-banner')
    expect(warningBanner).toHaveTextContent('API 額度已用盡，改由快取提供')
    expect(warningBanner).toHaveTextContent('歷史日 K 不足 5 年')
  })
})
