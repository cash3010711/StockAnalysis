import React, { useEffect, useRef } from 'react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineStyle,
} from 'lightweight-charts'
import type {
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  IPriceLine,
  SeriesMarker,
  Time,
} from 'lightweight-charts'
import type { OHLCVItem, StrategyItem } from '../types/api'

interface StockChartProps {
  ohlcv: OHLCVItem[]
  selectedStrategy?: StrategyItem | null
}

export const StockChart: React.FC<StockChartProps> = ({
  ohlcv,
  selectedStrategy,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const priceLinesRef = useRef<IPriceLine[]>([])

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return

    // In non-DOM or test environment where offsetWidth might be 0
    const container = chartContainerRef.current
    const width = container.clientWidth || 800
    const height = 480

    let chart: IChartApi
    try {
      chart = createChart(container, {
        width,
        height,
        layout: {
          background: { type: ColorType.Solid, color: '#ffffff' },
          textColor: '#334155',
        },
        grid: {
          vertLines: { color: '#f1f5f9' },
          horzLines: { color: '#f1f5f9' },
        },
        crosshair: {
          mode: 1, // Normal
        },
        rightPriceScale: {
          borderColor: '#cbd5e1',
          scaleMargins: {
            top: 0.1,
            bottom: 0.25,
          },
        },
        timeScale: {
          borderColor: '#cbd5e1',
          timeVisible: false,
        },
      })
    } catch {
      // In jsdom without canvas support, createChart may fail
      return
    }

    chartRef.current = chart

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#22c55e',
      borderVisible: false,
      wickUpColor: '#ef4444',
      wickDownColor: '#22c55e',
    })
    candleSeriesRef.current = candleSeries

    // Volume histogram series
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#94a3b8',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '', // overlay on same pane
    })
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    })
    volumeSeriesRef.current = volumeSeries

    // Resize handler
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
        candleSeriesRef.current = null
        volumeSeriesRef.current = null
        markersPluginRef.current = null
        priceLinesRef.current = []
      }
    }
  }, [])

  // Update OHLCV data
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || ohlcv.length === 0) {
      return
    }

    // Sort ascending by date
    const sorted = [...ohlcv].sort((a, b) => a.date.localeCompare(b.date))

    const candleData = sorted.map((d) => ({
      time: d.date,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))

    const volumeData = sorted.map((d) => ({
      time: d.date,
      value: d.volume,
      color: d.close >= d.open ? '#fca5a5' : '#86efac',
    }))

    candleSeriesRef.current.setData(candleData)
    volumeSeriesRef.current.setData(volumeData)

    if (chartRef.current) {
      chartRef.current.timeScale().fitContent()
    }
  }, [ohlcv])

  // Update Markers and Price Lines when selectedStrategy changes
  useEffect(() => {
    const candleSeries = candleSeriesRef.current
    if (!candleSeries) return

    // 1. Remove old price lines
    priceLinesRef.current.forEach((line) => {
      try {
        candleSeries.removePriceLine(line)
      } catch {
        // ignore
      }
    })
    priceLinesRef.current = []

    if (!selectedStrategy) {
      if (markersPluginRef.current) {
        markersPluginRef.current.setMarkers([])
      }
      return
    }

    // 2. Build markers from trades
    // Prioritize three_layer_trades, if none, use tech_only_trades
    const trades =
      selectedStrategy.three_layer_trades.length > 0
        ? selectedStrategy.three_layer_trades
        : selectedStrategy.tech_only_trades

    const markers: SeriesMarker<Time>[] = []

    trades.forEach((trade) => {
      // Entry marker
      markers.push({
        time: trade.entry_date,
        position: 'belowBar',
        color: '#2563eb',
        shape: 'arrowUp',
        text: `買進 ${trade.entry_price}`,
      })

      // Exit marker
      const win = trade.is_win
      const pctStr = `${(trade.net_return * 100).toFixed(1)}%`
      markers.push({
        time: trade.exit_date,
        position: 'aboveBar',
        color: win ? '#16a34a' : '#ef4444',
        shape: 'arrowDown',
        text: `${trade.exit_reason} ${win ? '獲利' : '停損'} ${pctStr}`,
      })
    })

    // Markers must be sorted by time ascending
    markers.sort((a, b) => (a.time as string).localeCompare(b.time as string))

    if (!markersPluginRef.current) {
      try {
        markersPluginRef.current = createSeriesMarkers(candleSeries, markers)
      } catch {
        // In mock environments
      }
    } else {
      markersPluginRef.current.setMarkers(markers)
    }

    // 3. Add price lines if today is entry status
    const isEntry =
      selectedStrategy.status === '進場' || selectedStrategy.action === '進場'

    if (isEntry) {
      if (selectedStrategy.entry_price != null) {
        const line = candleSeries.createPriceLine({
          price: selectedStrategy.entry_price,
          color: '#2563eb',
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: `進場價 ${selectedStrategy.entry_price}`,
        })
        priceLinesRef.current.push(line)
      }

      if (selectedStrategy.stop_loss != null) {
        const line = candleSeries.createPriceLine({
          price: selectedStrategy.stop_loss,
          color: '#dc2626',
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `停損價 ${selectedStrategy.stop_loss}`,
        })
        priceLinesRef.current.push(line)
      }

      if (selectedStrategy.take_profit != null) {
        const line = candleSeries.createPriceLine({
          price: selectedStrategy.take_profit,
          color: '#16a34a',
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `停利價 ${selectedStrategy.take_profit}`,
        })
        priceLinesRef.current.push(line)
      }
    }
  }, [selectedStrategy])

  return (
    <div
      style={{
        marginTop: '24px',
        padding: '16px',
        background: '#ffffff',
        borderRadius: '8px',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
      }}
      data-testid="stock-chart-card"
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '12px',
        }}
      >
        <h3 style={{ margin: 0, fontSize: '18px', color: '#1e293b' }}>
          K 線圖與交易訊號
          {selectedStrategy && (
            <span
              style={{
                marginLeft: '8px',
                fontSize: '14px',
                color: '#3b82f6',
                fontWeight: 'normal',
              }}
            >
              (當前策略：{selectedStrategy.strategy_name})
            </span>
          )}
        </h3>

        <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: '#64748b' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span
              style={{
                display: 'inline-block',
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: '#2563eb',
              }}
            />
            進場點
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span
              style={{
                display: 'inline-block',
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: '#16a34a',
              }}
            />
            獲利出場
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span
              style={{
                display: 'inline-block',
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: '#ef4444',
              }}
            />
            停損出場
          </span>
        </div>
      </div>

      <div
        ref={chartContainerRef}
        data-testid="chart-container"
        style={{ width: '100%', height: '480px', position: 'relative' }}
      />
    </div>
  )
}
