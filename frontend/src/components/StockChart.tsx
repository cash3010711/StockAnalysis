import React, { useEffect, useRef, useState } from 'react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
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
import type { InstitutionalItem, OHLCVItem, StrategyItem } from '../types/api'

interface StockChartProps {
  ohlcv: OHLCVItem[]
  institutional?: InstitutionalItem[]
  selectedStrategy?: StrategyItem | null
}

const formatValue = (val: number | null | undefined): string => {
  if (val == null || Number.isNaN(val)) return '-'
  return Number(val).toFixed(2)
}

export const StockChart: React.FC<StockChartProps> = ({
  ohlcv,
  institutional,
  selectedStrategy,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const instSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const ma5SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma10SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma20SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma60SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma120SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const bbUpperSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const bbLowerSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const priceLinesRef = useRef<IPriceLine[]>([])

  // Subpane mode: volume vs institutional
  const [subPane, setSubPane] = useState<'volume' | 'institutional'>('volume')

  // Indicator layer toggle states
  const [visibleLayers, setVisibleLayers] = useState({
    ma5: true,
    ma10: true,
    ma20: true,
    ma60: false,
    ma120: false,
    bollinger: true,
  })

  // Crosshair dynamic hover indicator state
  const [hoveredData, setHoveredData] = useState<OHLCVItem | null>(null)
  const latestDataRef = useRef<OHLCVItem | null>(null)
  const ohlcvMapRef = useRef<Map<string, OHLCVItem>>(new Map())

  // Institutional hover data
  const [hoveredInst, setHoveredInst] = useState<InstitutionalItem | null>(null)
  const latestInstRef = useRef<InstitutionalItem | null>(null)
  const instMapRef = useRef<Map<string, InstitutionalItem>>(new Map())

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

    // Institutional net buy/sell histogram series (三大法人副圖)
    const instSeries = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '', // overlay on same bottom subpane
      visible: false,
    })
    instSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    })
    instSeriesRef.current = instSeries

    // MA5 series (琥珀黃實線)
    const ma5Series = chart.addSeries(LineSeries, {
      color: '#f59e0b',
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    ma5SeriesRef.current = ma5Series

    // MA10 series (紫色實線)
    const ma10Series = chart.addSeries(LineSeries, {
      color: '#a855f7',
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    ma10SeriesRef.current = ma10Series

    // MA20 / 布林中軌 series (藍色實線 2px)
    const ma20Series = chart.addSeries(LineSeries, {
      color: '#3b82f6',
      lineWidth: 2,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    ma20SeriesRef.current = ma20Series

    // MA60 series (森林綠色實線)
    const ma60Series = chart.addSeries(LineSeries, {
      color: '#10b981',
      lineWidth: 2,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
      lastValueVisible: false,
      visible: false,
    })
    ma60SeriesRef.current = ma60Series

    // MA120 series (磚紅色實線)
    const ma120Series = chart.addSeries(LineSeries, {
      color: '#c2410c',
      lineWidth: 2,
      lineStyle: LineStyle.Solid,
      priceLineVisible: false,
      lastValueVisible: false,
      visible: false,
    })
    ma120SeriesRef.current = ma120Series

    // 布林上軌 series (冷灰色細虛線 1px)
    const bbUpperSeries = chart.addSeries(LineSeries, {
      color: '#64748b',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    bbUpperSeriesRef.current = bbUpperSeries

    // 布林下軌 series (冷灰色細虛線 1px)
    const bbLowerSeries = chart.addSeries(LineSeries, {
      color: '#64748b',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    bbLowerSeriesRef.current = bbLowerSeries

    // Subscribe crosshair move for dynamic legend
    chart.subscribeCrosshairMove((param) => {
      if (
        !param ||
        !param.time ||
        param.point === undefined ||
        param.point.x < 0 ||
        param.point.y < 0
      ) {
        setHoveredData(latestDataRef.current)
        setHoveredInst(latestInstRef.current)
        return
      }

      const timeStr =
        typeof param.time === 'string'
          ? param.time
          : typeof param.time === 'object' && param.time !== null
            ? `${(param.time as { year: number }).year}-${String((param.time as { month: number }).month).padStart(2, '0')}-${String((param.time as { day: number }).day).padStart(2, '0')}`
            : String(param.time)

      const item = ohlcvMapRef.current.get(timeStr)
      if (item) {
        setHoveredData(item)
      } else {
        setHoveredData(latestDataRef.current)
      }

      const instItem = instMapRef.current.get(timeStr)
      if (instItem) {
        setHoveredInst(instItem)
      } else {
        setHoveredInst(latestInstRef.current)
      }
    })

    const handleMouseLeave = () => {
      setHoveredData(latestDataRef.current)
      setHoveredInst(latestInstRef.current)
    }

    container.addEventListener('mouseleave', handleMouseLeave)

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
      container.removeEventListener('mouseleave', handleMouseLeave)
      window.removeEventListener('resize', handleResize)
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
        candleSeriesRef.current = null
        volumeSeriesRef.current = null
        instSeriesRef.current = null
        ma5SeriesRef.current = null
        ma10SeriesRef.current = null
        ma20SeriesRef.current = null
        ma60SeriesRef.current = null
        ma120SeriesRef.current = null
        bbUpperSeriesRef.current = null
        bbLowerSeriesRef.current = null
        markersPluginRef.current = null
        priceLinesRef.current = []
      }
    }
  }, [])

  // Apply visibility options when toggle states change
  useEffect(() => {
    ma5SeriesRef.current?.applyOptions({ visible: visibleLayers.ma5 })
    ma10SeriesRef.current?.applyOptions({ visible: visibleLayers.ma10 })
    ma20SeriesRef.current?.applyOptions({ visible: visibleLayers.ma20 })
    ma60SeriesRef.current?.applyOptions({ visible: visibleLayers.ma60 })
    ma120SeriesRef.current?.applyOptions({ visible: visibleLayers.ma120 })
    bbUpperSeriesRef.current?.applyOptions({ visible: visibleLayers.bollinger })
    bbLowerSeriesRef.current?.applyOptions({ visible: visibleLayers.bollinger })
  }, [visibleLayers])

  // Apply subpane toggle options (成交量 vs 三大法人)
  useEffect(() => {
    volumeSeriesRef.current?.applyOptions({ visible: subPane === 'volume' })
    instSeriesRef.current?.applyOptions({ visible: subPane === 'institutional' })
  }, [subPane])

  // Update Institutional data
  useEffect(() => {
    if (!institutional || institutional.length === 0) {
      latestInstRef.current = null
      instMapRef.current = new Map()
      setHoveredInst(null)
      return
    }

    const sortedInst = [...institutional].sort((a, b) => a.date.localeCompare(b.date))
    const map = new Map<string, InstitutionalItem>()
    sortedInst.forEach((item) => map.set(item.date, item))
    instMapRef.current = map

    const latest = sortedInst[sortedInst.length - 1]
    latestInstRef.current = latest
    setHoveredInst(latest)

    if (instSeriesRef.current) {
      const instData = sortedInst.map((item) => ({
        time: item.date as Time,
        value: item.total_net,
        color: item.total_net >= 0 ? '#ef4444' : '#3b82f6',
      }))
      instSeriesRef.current.setData(instData)
    }
  }, [institutional])

  // Update OHLCV data
  useEffect(() => {
    if (ohlcv.length === 0) {
      latestDataRef.current = null
      ohlcvMapRef.current = new Map()
      setHoveredData(null)
      return
    }

    // Sort ascending by date
    const sorted = [...ohlcv].sort((a, b) => a.date.localeCompare(b.date))
    const map = new Map<string, OHLCVItem>()
    sorted.forEach((item) => map.set(item.date, item))
    ohlcvMapRef.current = map

    const latest = sorted[sorted.length - 1]
    latestDataRef.current = latest
    setHoveredData(latest)

    if (!candleSeriesRef.current || !volumeSeriesRef.current) {
      return
    }

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

    const ma5Data = sorted
      .filter((d) => d.ma5 != null)
      .map((d) => ({ time: d.date as Time, value: d.ma5! }))
    const ma10Data = sorted
      .filter((d) => d.ma10 != null)
      .map((d) => ({ time: d.date as Time, value: d.ma10! }))
    const ma20Data = sorted
      .filter((d) => d.ma20 != null)
      .map((d) => ({ time: d.date as Time, value: d.ma20! }))
    const ma60Data = sorted
      .filter((d) => d.ma60 != null)
      .map((d) => ({ time: d.date as Time, value: d.ma60! }))
    const ma120Data = sorted
      .filter((d) => d.ma120 != null)
      .map((d) => ({ time: d.date as Time, value: d.ma120! }))
    const bbUpperData = sorted
      .filter((d) => d.bb_upper != null)
      .map((d) => ({ time: d.date as Time, value: d.bb_upper! }))
    const bbLowerData = sorted
      .filter((d) => d.bb_lower != null)
      .map((d) => ({ time: d.date as Time, value: d.bb_lower! }))

    ma5SeriesRef.current?.setData(ma5Data)
    ma10SeriesRef.current?.setData(ma10Data)
    ma20SeriesRef.current?.setData(ma20Data)
    ma60SeriesRef.current?.setData(ma60Data)
    ma120SeriesRef.current?.setData(ma120Data)
    bbUpperSeriesRef.current?.setData(bbUpperData)
    bbLowerSeriesRef.current?.setData(bbLowerData)

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

      {/* Indicator Controls & Dynamic Legend Bar */}
      <div
        data-testid="chart-toolbar"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '12px',
          padding: '8px 12px',
          marginBottom: '12px',
          background: '#f8fafc',
          borderRadius: '6px',
          border: '1px solid #e2e8f0',
          fontSize: '12px',
        }}
      >
        {/* Toggle Buttons */}
        <div
          data-testid="layer-controls"
          style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}
        >
          <span style={{ fontWeight: 600, color: '#475569', marginRight: '4px' }}>圖層開關:</span>
          <button
            type="button"
            data-testid="toggle-ma5"
            onClick={() => setVisibleLayers((prev) => ({ ...prev, ma5: !prev.ma5 }))}
            style={{
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 500,
              border: visibleLayers.ma5 ? '1px solid #f59e0b' : '1px solid #cbd5e1',
              background: visibleLayers.ma5 ? '#fef3c7' : '#ffffff',
              color: visibleLayers.ma5 ? '#b45309' : '#94a3b8',
              transition: 'all 0.15s ease',
            }}
          >
            {visibleLayers.ma5 ? '[✓] 5MA' : '[ ] 5MA'}
          </button>
          <button
            type="button"
            data-testid="toggle-ma10"
            onClick={() => setVisibleLayers((prev) => ({ ...prev, ma10: !prev.ma10 }))}
            style={{
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 500,
              border: visibleLayers.ma10 ? '1px solid #a855f7' : '1px solid #cbd5e1',
              background: visibleLayers.ma10 ? '#f3e8ff' : '#ffffff',
              color: visibleLayers.ma10 ? '#7e22ce' : '#94a3b8',
              transition: 'all 0.15s ease',
            }}
          >
            {visibleLayers.ma10 ? '[✓] 10MA' : '[ ] 10MA'}
          </button>
          <button
            type="button"
            data-testid="toggle-ma20"
            onClick={() => setVisibleLayers((prev) => ({ ...prev, ma20: !prev.ma20 }))}
            style={{
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 500,
              border: visibleLayers.ma20 ? '1px solid #3b82f6' : '1px solid #cbd5e1',
              background: visibleLayers.ma20 ? '#dbeafe' : '#ffffff',
              color: visibleLayers.ma20 ? '#1d4ed8' : '#94a3b8',
              transition: 'all 0.15s ease',
            }}
          >
            {visibleLayers.ma20 ? '[✓] 20MA' : '[ ] 20MA'}
          </button>
          <button
            type="button"
            data-testid="toggle-ma60"
            onClick={() => setVisibleLayers((prev) => ({ ...prev, ma60: !prev.ma60 }))}
            style={{
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 500,
              border: visibleLayers.ma60 ? '1px solid #10b981' : '1px solid #cbd5e1',
              background: visibleLayers.ma60 ? '#d1fae5' : '#ffffff',
              color: visibleLayers.ma60 ? '#047857' : '#94a3b8',
              transition: 'all 0.15s ease',
            }}
          >
            {visibleLayers.ma60 ? '[✓] 60MA' : '[ ] 60MA'}
          </button>
          <button
            type="button"
            data-testid="toggle-ma120"
            onClick={() => setVisibleLayers((prev) => ({ ...prev, ma120: !prev.ma120 }))}
            style={{
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 500,
              border: visibleLayers.ma120 ? '1px solid #c2410c' : '1px solid #cbd5e1',
              background: visibleLayers.ma120 ? '#ffedd5' : '#ffffff',
              color: visibleLayers.ma120 ? '#9a3412' : '#94a3b8',
              transition: 'all 0.15s ease',
            }}
          >
            {visibleLayers.ma120 ? '[✓] 120MA' : '[ ] 120MA'}
          </button>
          <button
            type="button"
            data-testid="toggle-bollinger"
            onClick={() => setVisibleLayers((prev) => ({ ...prev, bollinger: !prev.bollinger }))}
            style={{
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 500,
              border: visibleLayers.bollinger ? '1px solid #64748b' : '1px solid #cbd5e1',
              background: visibleLayers.bollinger ? '#f1f5f9' : '#ffffff',
              color: visibleLayers.bollinger ? '#334155' : '#94a3b8',
              transition: 'all 0.15s ease',
            }}
          >
            {visibleLayers.bollinger ? '[✓] 布林通道' : '[ ] 布林通道'}
          </button>
        </div>

        {/* Subpane Controls (成交量 vs 三大法人) */}
        <div
          data-testid="subpane-controls"
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <span style={{ fontWeight: 600, color: '#475569', marginRight: '4px' }}>副圖:</span>
          <button
            type="button"
            data-testid="subpane-volume"
            onClick={() => setSubPane('volume')}
            style={{
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 500,
              border: subPane === 'volume' ? '1px solid #2563eb' : '1px solid #cbd5e1',
              background: subPane === 'volume' ? '#dbeafe' : '#ffffff',
              color: subPane === 'volume' ? '#1d4ed8' : '#64748b',
              transition: 'all 0.15s ease',
            }}
          >
            {subPane === 'volume' ? '● 成交量' : '○ 成交量'}
          </button>
          <button
            type="button"
            data-testid="subpane-institutional"
            onClick={() => setSubPane('institutional')}
            style={{
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 500,
              border: subPane === 'institutional' ? '1px solid #2563eb' : '1px solid #cbd5e1',
              background: subPane === 'institutional' ? '#dbeafe' : '#ffffff',
              color: subPane === 'institutional' ? '#1d4ed8' : '#64748b',
              transition: 'all 0.15s ease',
            }}
          >
            {subPane === 'institutional' ? '● 三大法人' : '○ 三大法人'}
          </button>
        </div>

        {/* Dynamic Legend */}
        <div
          data-testid="chart-legend"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            flexWrap: 'wrap',
            fontSize: '12px',
            color: '#334155',
            fontFamily: 'monospace',
          }}
        >
          {hoveredData?.date && (
            <span data-testid="legend-date" style={{ color: '#64748b', fontWeight: 600 }}>
              {hoveredData.date}
            </span>
          )}
          <span
            data-testid="legend-ma5"
            style={{
              color: '#b45309',
              opacity: visibleLayers.ma5 ? 1 : 0.4,
              fontWeight: 500,
            }}
          >
            5MA: {formatValue(hoveredData?.ma5)}
          </span>
          <span
            data-testid="legend-ma10"
            style={{
              color: '#7e22ce',
              opacity: visibleLayers.ma10 ? 1 : 0.4,
              fontWeight: 500,
            }}
          >
            10MA: {formatValue(hoveredData?.ma10)}
          </span>
          <span
            data-testid="legend-ma20"
            style={{
              color: '#1d4ed8',
              opacity: visibleLayers.ma20 ? 1 : 0.4,
              fontWeight: 500,
            }}
          >
            20MA / 布林中軌: {formatValue(hoveredData?.ma20 ?? hoveredData?.bb_mid)}
          </span>
          <span
            data-testid="legend-ma60"
            style={{
              color: '#047857',
              opacity: visibleLayers.ma60 ? 1 : 0.4,
              fontWeight: 500,
            }}
          >
            60MA: {formatValue(hoveredData?.ma60)}
          </span>
          <span
            data-testid="legend-ma120"
            style={{
              color: '#9a3412',
              opacity: visibleLayers.ma120 ? 1 : 0.4,
              fontWeight: 500,
            }}
          >
            120MA: {formatValue(hoveredData?.ma120)}
          </span>
          <span
            data-testid="legend-bb-upper"
            style={{
              color: '#475569',
              opacity: visibleLayers.bollinger ? 1 : 0.4,
              fontWeight: 500,
            }}
          >
            布林上軌: {formatValue(hoveredData?.bb_upper)}
          </span>
          <span
            data-testid="legend-bb-lower"
            style={{
              color: '#475569',
              opacity: visibleLayers.bollinger ? 1 : 0.4,
              fontWeight: 500,
            }}
          >
            布林下軌: {formatValue(hoveredData?.bb_lower)}
          </span>

          {/* Subpane Dynamic Display */}
          {subPane === 'volume' ? (
            <span
              data-testid="legend-volume"
              style={{
                color: '#64748b',
                fontWeight: 600,
                borderLeft: '1px solid #cbd5e1',
                paddingLeft: '8px',
              }}
            >
              量: {hoveredData?.volume != null ? hoveredData.volume.toLocaleString() : '-'}
            </span>
          ) : (
            <div
              data-testid="institutional-legend"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                borderLeft: '1px solid #cbd5e1',
                paddingLeft: '8px',
              }}
            >
              <span
                data-testid="legend-inst-foreign"
                style={{
                  color: (hoveredInst?.foreign_net ?? 0) >= 0 ? '#ef4444' : '#2563eb',
                  fontWeight: 500,
                }}
              >
                外資: {hoveredInst?.foreign_net != null ? `${hoveredInst.foreign_net > 0 ? '+' : ''}${hoveredInst.foreign_net.toFixed(1)}張` : '-'}
              </span>
              <span
                data-testid="legend-inst-trust"
                style={{
                  color: (hoveredInst?.investment_trust_net ?? 0) >= 0 ? '#ef4444' : '#2563eb',
                  fontWeight: 500,
                }}
              >
                投信: {hoveredInst?.investment_trust_net != null ? `${hoveredInst.investment_trust_net > 0 ? '+' : ''}${hoveredInst.investment_trust_net.toFixed(1)}張` : '-'}
              </span>
              <span
                data-testid="legend-inst-dealer"
                style={{
                  color: (hoveredInst?.dealer_net ?? 0) >= 0 ? '#ef4444' : '#2563eb',
                  fontWeight: 500,
                }}
              >
                自營: {hoveredInst?.dealer_net != null ? `${hoveredInst.dealer_net > 0 ? '+' : ''}${hoveredInst.dealer_net.toFixed(1)}張` : '-'}
              </span>
              <span
                data-testid="legend-inst-total"
                style={{
                  color: (hoveredInst?.total_net ?? 0) >= 0 ? '#ef4444' : '#2563eb',
                  fontWeight: 700,
                }}
              >
                合計: {hoveredInst?.total_net != null ? `${hoveredInst.total_net > 0 ? '+' : ''}${hoveredInst.total_net.toFixed(1)}張` : '-'}
              </span>
            </div>
          )}
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
