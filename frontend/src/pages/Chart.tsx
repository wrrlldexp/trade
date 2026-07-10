import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  createChart,
  type IChartApi,
  ColorType,
  LineStyle,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";

import { apiClient } from "../api/client";
import { listGrids, listGridOrders } from "../api/grids";
import type { Grid, GridOrder } from "../api/types";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import {
  resolveOrderLabelLayout,
  type OrderForLayout,
  type LabelGroup,
} from "../utils/resolveOrderLabelLayout";

// ─── Types ───

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface TickerData {
  bid: number;
  ask: number;
  last: number;
  symbol: string;
}

// ─── Helpers ───

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"] as const;

const ORDER_COLORS: Record<string, { buy: string; sell: string }> = {
  placed: { buy: "#22c55e", sell: "#ef4444" },
  wait: { buy: "#a3e635", sell: "#fb923c" },
};

const STRATEGY_LABELS: Record<string, string> = {
  simple: "Простая",
  capitalization: "Капитализация",
  reverse: "Реверс",
  reverse_cap: "Реверс+Кап",
  adaptive: "Адаптивная",
  adaptive_cap: "Адаптивная+Кап",
};

function getExchangeFromGrid(_grid: Grid): string {
  return "bybit";
}

function formatPrice(price: number, symbol: string): string {
  if (symbol.startsWith("BTC")) return price.toFixed(1);
  if (symbol.startsWith("SOL") || symbol.startsWith("ETH")) return price.toFixed(2);
  return price.toFixed(4);
}

function formatRu(date: string) {
  return new Date(date).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(ms: number): string {
  const min = Math.round(ms / 60000);
  if (min < 1) return "<1м";
  if (min < 60) return `${min}м`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h < 24) return m ? `${h}ч ${m}м` : `${h}ч`;
  const d = Math.floor(h / 24);
  return `${d}д ${h % 24}ч`;
}

function formatPnl(value: number): string {
  const sign = value >= 0 ? "+" : "";
  const abs = Math.abs(value);
  const decimals = abs > 0 && abs < 0.01 ? 8 : abs < 1 ? 4 : 2;
  const formatted = value.toFixed(decimals).replace(/0+$/, "").replace(/\.$/, "");
  return `${sign}${formatted}`;
}

function formatVol(v: number): string {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(1) + "K";
  return v.toFixed(0);
}

// ─── Indicator calculations ───

function calcSMA(data: Candle[], period: number): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}

function calcEMA(data: Candle[], period: number): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  const k = 2 / (period + 1);
  let ema = data[0]?.close ?? 0;
  for (let i = 0; i < data.length; i++) {
    ema = data[i].close * k + ema * (1 - k);
    if (i >= period - 1) {
      result.push({ time: data[i].time, value: ema });
    }
  }
  return result;
}

function calcBollingerBands(data: Candle[], period: number, stdDev: number) {
  const upper: { time: number; value: number }[] = [];
  const lower: { time: number; value: number }[] = [];
  const mid: { time: number; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    const mean = sum / period;
    let sqSum = 0;
    for (let j = 0; j < period; j++) sqSum += (data[i - j].close - mean) ** 2;
    const std = Math.sqrt(sqSum / period);
    mid.push({ time: data[i].time, value: mean });
    upper.push({ time: data[i].time, value: mean + stdDev * std });
    lower.push({ time: data[i].time, value: mean - stdDev * std });
  }
  return { upper, mid, lower };
}

function calcVWAP(data: Candle[]): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  let cumVol = 0;
  let cumTP = 0;
  for (const c of data) {
    const tp = (c.high + c.low + c.close) / 3;
    cumVol += c.volume;
    cumTP += tp * c.volume;
    if (cumVol > 0) {
      result.push({ time: c.time, value: cumTP / cumVol });
    }
  }
  return result;
}

// ─── API ───

async function fetchCandles(
  exchange: string,
  symbol: string,
  timeframe: string,
): Promise<Candle[]> {
  const { data } = await apiClient.get<Candle[]>("/api/market/ohlcv", {
    params: { exchange, symbol, timeframe, limit: 500 },
  });
  return data;
}

async function fetchTicker(
  exchange: string,
  symbol: string,
): Promise<TickerData> {
  const { data } = await apiClient.get<TickerData>("/api/market/ticker", {
    params: { exchange, symbol },
  });
  return data;
}

// ─── Indicator config ───

type IndicatorId = "ma7" | "ma25" | "ma99" | "ema12" | "ema26" | "bb" | "vol" | "vwap";

interface IndicatorDef {
  id: IndicatorId;
  label: string;
  group: string;
}

const INDICATORS: IndicatorDef[] = [
  { id: "ma7", label: "MA 7", group: "MA" },
  { id: "ma25", label: "MA 25", group: "MA" },
  { id: "ma99", label: "MA 99", group: "MA" },
  { id: "ema12", label: "EMA 12", group: "EMA" },
  { id: "ema26", label: "EMA 26", group: "EMA" },
  { id: "bb", label: "Боллинджер", group: "BB" },
  { id: "vwap", label: "VWAP", group: "VWAP" },
  { id: "vol", label: "Объём", group: "Vol" },
];

const IND_COLORS: Record<string, string> = {
  ma7: "#f59e0b",
  ma25: "#3b82f6",
  ma99: "#a855f7",
  ema12: "#f97316",
  ema26: "#06b6d4",
  bb_upper: "#6366f180",
  bb_mid: "#6366f1",
  bb_lower: "#6366f180",
  vwap: "#ec4899",
};

// ─── Density mode (Task 4) ───

function useDensityMode() {
  const [compact, setCompact] = useState(() => {
    try {
      return localStorage.getItem("chart:density") === "compact";
    } catch {
      return false;
    }
  });
  const toggle = useCallback(() => {
    setCompact((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("chart:density", next ? "compact" : "full");
      } catch { /* ignore */ }
      return next;
    });
  }, []);
  return { compact, toggle };
}

// ─── Order Label Overlay (Task 1) ───

const LABEL_TONE_COLORS = {
  buy: { bg: "rgba(34,197,94,0.15)", border: "rgba(34,197,94,0.4)", text: "#4ade80" },
  sell: { bg: "rgba(239,68,68,0.15)", border: "rgba(239,68,68,0.4)", text: "#f87171" },
  mixed: { bg: "rgba(251,191,36,0.15)", border: "rgba(251,191,36,0.4)", text: "#fbbf24" },
};

function OrderLabelOverlay({
  groups,
  chartHeight,
  symbol,
}: {
  groups: LabelGroup[];
  chartHeight: number;
  symbol: string;
}) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const fp = (p: number) => formatPrice(p, symbol);

  return (
    <div
      className="absolute top-0 right-0 z-20 pointer-events-auto"
      style={{ height: chartHeight, width: 220 }}
    >
      {groups.map((g, idx) => {
        const colors = LABEL_TONE_COLORS[g.tone];
        const isHovered = hoveredIdx === idx;
        const isMulti = g.orders.length > 1;

        return (
          <div
            key={idx}
            className="absolute right-2 transition-all duration-150"
            style={{ top: Math.max(0, Math.min(g.y - 10, chartHeight - 24)) }}
            onMouseEnter={() => setHoveredIdx(idx)}
            onMouseLeave={() => setHoveredIdx(null)}
          >
            {/* Label pill */}
            <div
              className="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium whitespace-nowrap cursor-default select-none"
              style={{
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                color: colors.text,
              }}
            >
              {g.label}
              {isMulti && (
                <span className="ml-0.5 text-[9px] opacity-60">({g.orders.length})</span>
              )}
            </div>

            {/* Tooltip on hover for multi-order groups */}
            {isHovered && isMulti && (
              <div
                className="absolute right-0 top-full mt-1 z-30 rounded-lg border border-white/10 bg-[#0b1220] p-3 shadow-xl"
                style={{ minWidth: 240 }}
              >
                <div className="text-[10px] text-white/30 uppercase tracking-wider mb-2">
                  Группа ордеров · {fp(g.minPrice)}–{fp(g.maxPrice)}
                </div>
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="text-white/25 text-[9px] uppercase">
                      <th className="pb-1 text-left">ID</th>
                      <th className="pb-1 text-left">Тип</th>
                      <th className="pb-1 text-right">Цена</th>
                      <th className="pb-1 text-right">Объём</th>
                      <th className="pb-1 text-center">Статус</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.orders.map((o) => (
                      <tr key={o.id} className="border-t border-white/[0.04]">
                        <td className="py-1 text-white/50">
                          {o.side === "buy" ? "B" : "S"}#{o.gridIndex}
                        </td>
                        <td className={`py-1 ${o.side === "buy" ? "text-emerald-400" : "text-red-400"}`}>
                          {o.side === "buy" ? "BUY" : "SELL"}
                        </td>
                        <td className="py-1 text-right text-white/70 tabular-nums">
                          {fp(o.side === "buy" ? o.price : o.priceSell)}
                        </td>
                        <td className="py-1 text-right text-white/40 tabular-nums">
                          {o.amount.toFixed(6)}
                        </td>
                        <td className="py-1 text-center">
                          <span className={`text-[9px] ${o.status === "placed" ? "text-emerald-400" : "text-amber-400"}`}>
                            {o.status === "placed" ? "На бирже" : "Ожидание"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Filter chips (Task 2) ───

type OrderFilter = "all" | "buy" | "sell" | "placed" | "wait";
type OrderSort = "index" | "price";

const FILTER_CHIPS: { key: OrderFilter; label: string }[] = [
  { key: "all", label: "Все" },
  { key: "buy", label: "Buy" },
  { key: "sell", label: "Sell" },
  { key: "placed", label: "На бирже" },
  { key: "wait", label: "Ожидание" },
];

function filterOrders(orders: GridOrder[], filter: OrderFilter): GridOrder[] {
  switch (filter) {
    case "buy":
      return orders.filter((o) => o.side === "buy");
    case "sell":
      return orders.filter((o) => o.side === "sell");
    case "placed":
      return orders.filter((o) => o.status === "placed");
    case "wait":
      return orders.filter((o) => o.status === "wait");
    default:
      return orders;
  }
}

function sortOrders(orders: GridOrder[], sort: OrderSort): GridOrder[] {
  const sorted = [...orders];
  if (sort === "price") {
    sorted.sort((a, b) => Number(a.price) - Number(b.price));
  } else {
    sorted.sort((a, b) => a.grid_index - b.grid_index);
  }
  return sorted;
}

// ─── Chart Component ───

export function ChartPage() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const candleSeriesRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const indicatorSeriesRef = useRef<Map<string, any>>(new Map());
  const priceLineRefs = useRef<Map<string, unknown>>(new Map());
  const tickerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [selectedGridId, setSelectedGridId] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<(typeof TIMEFRAMES)[number]>("5m");
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [prevPrice, setPrevPrice] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(true);
  const [tradesLimit, setTradesLimit] = useState(20);
  const [activeIndicators, setActiveIndicators] = useState<Set<IndicatorId>>(new Set(["vol"]));
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [crosshairData, setCrosshairData] = useState<{
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    change: number;
    changePct: number;
  } | null>(null);

  // Task 1: label groups
  const [labelGroups, setLabelGroups] = useState<LabelGroup[]>([]);

  // Task 2: filter & sort
  const [orderFilter, setOrderFilter] = useState<OrderFilter>("all");
  const [orderSort, setOrderSort] = useState<OrderSort>("index");

  // Task 4: density mode
  const { compact, toggle: toggleDensity } = useDensityMode();

  const toggleIndicator = (id: IndicatorId) => {
    setActiveIndicators((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Fetch grids
  const { data: grids } = useQuery({
    queryKey: ["grids"],
    queryFn: listGrids,
    refetchInterval: 30_000,
  });

  const runningGrids = grids?.filter((g) => g.status === "running") ?? [];

  useEffect(() => {
    if (!selectedGridId && runningGrids.length > 0) {
      setSelectedGridId(runningGrids[0].id);
    }
  }, [runningGrids, selectedGridId]);

  const selectedGrid = grids?.find((g) => g.id === selectedGridId) ?? null;
  const exchange = selectedGrid ? getExchangeFromGrid(selectedGrid) : "bybit";
  const symbol = selectedGrid?.symbol ?? "BTC/USDT";

  const { data: orders } = useQuery({
    queryKey: ["grid-orders", selectedGridId],
    queryFn: () => (selectedGridId ? listGridOrders(selectedGridId) : Promise.resolve([])),
    enabled: !!selectedGridId,
    refetchInterval: 5_000,
  });

  const { data: candles } = useQuery({
    queryKey: ["candles", exchange, symbol, timeframe],
    queryFn: () => fetchCandles(exchange, symbol, timeframe),
    enabled: !!symbol,
    refetchInterval: 30_000,
  });

  const allGridOrdersQueries = useQueries({
    queries: runningGrids.map((g) => ({
      queryKey: ["grid-orders", g.id],
      queryFn: () => listGridOrders(g.id),
      refetchInterval: 10_000,
    })),
  });

  const allGridTrades = useMemo(() => {
    return runningGrids
      .map((g, i) => {
        const data = allGridOrdersQueries[i]?.data;
        const filled = (data?.filter((o) => o.status === "filled") ?? []).sort(
          (a, b) => {
            const ta = a.filled_at ?? a.created_at;
            const tb = b.filled_at ?? b.created_at;
            return new Date(tb).getTime() - new Date(ta).getTime();
          },
        );
        const totalProfit = filled.reduce((s, o) => s + Number(o.profit), 0);
        const sellCount = filled.filter((o) => o.side === "sell" && Number(o.profit) > 0).length;
        return { grid: g, trades: filled, totalProfit, sellCount };
      })
      .filter((x) => x.trades.length > 0);
  }, [runningGrids, allGridOrdersQueries]);

  // ─── Create chart ───
  const chartHeight = isFullscreen ? window.innerHeight - 120 : 520;

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgba(255,255,255,0.5)",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.025)" },
        horzLines: { color: "rgba(255,255,255,0.025)" },
      },
      crosshair: {
        mode: 0,
        horzLine: { color: "rgba(255,255,255,0.15)", style: LineStyle.Dashed, labelBackgroundColor: "#374151" },
        vertLine: { color: "rgba(255,255,255,0.15)", style: LineStyle.Dashed, labelBackgroundColor: "#374151" },
      },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.06)",
        scaleMargins: { top: 0.08, bottom: activeIndicators.has("vol") ? 0.25 : 0.08 },
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.06)",
        timeVisible: true,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: chartHeight,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef444499",
      wickUpColor: "#22c55e99",
    });

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) {
        setCrosshairData(null);
        return;
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const d = param.seriesData.get(series) as any;
      if (d && d.open !== undefined) {
        const change = d.close - d.open;
        const changePct = d.open !== 0 ? (change / d.open) * 100 : 0;
        setCrosshairData({
          time: new Date((param.time as number) * 1000).toLocaleString("ru-RU"),
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
          volume: 0,
          change,
          changePct,
        });
      }
    });

    chartRef.current = chart;
    candleSeriesRef.current = series;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      indicatorSeriesRef.current.clear();
    };
  }, [isFullscreen]);

  // ─── Update chart height when indicators change ───
  useEffect(() => {
    if (!chartRef.current) return;
    chartRef.current.applyOptions({
      rightPriceScale: {
        scaleMargins: { top: 0.08, bottom: activeIndicators.has("vol") ? 0.25 : 0.08 },
      },
    });
  }, [activeIndicators]);

  // ─── Update candles ───
  useEffect(() => {
    if (!candleSeriesRef.current || !candles?.length) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    candleSeriesRef.current.setData(candles as any);
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  // ─── Update indicators ───
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !candles?.length) return;

    for (const [, series] of indicatorSeriesRef.current.entries()) {
      try {
        chart.removeSeries(series);
      } catch { /* already removed */ }
    }
    indicatorSeriesRef.current.clear();

    if (activeIndicators.has("ma7")) {
      const s = chart.addSeries(LineSeries, {
        color: IND_COLORS.ma7,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      s.setData(calcSMA(candles, 7) as any);
      indicatorSeriesRef.current.set("ma7", s);
    }
    if (activeIndicators.has("ma25")) {
      const s = chart.addSeries(LineSeries, {
        color: IND_COLORS.ma25,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      s.setData(calcSMA(candles, 25) as any);
      indicatorSeriesRef.current.set("ma25", s);
    }
    if (activeIndicators.has("ma99")) {
      const s = chart.addSeries(LineSeries, {
        color: IND_COLORS.ma99,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      s.setData(calcSMA(candles, 99) as any);
      indicatorSeriesRef.current.set("ma99", s);
    }

    if (activeIndicators.has("ema12")) {
      const s = chart.addSeries(LineSeries, {
        color: IND_COLORS.ema12,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      s.setData(calcEMA(candles, 12) as any);
      indicatorSeriesRef.current.set("ema12", s);
    }
    if (activeIndicators.has("ema26")) {
      const s = chart.addSeries(LineSeries, {
        color: IND_COLORS.ema26,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      s.setData(calcEMA(candles, 26) as any);
      indicatorSeriesRef.current.set("ema26", s);
    }

    if (activeIndicators.has("bb")) {
      const bb = calcBollingerBands(candles, 20, 2);
      const sUpper = chart.addSeries(LineSeries, {
        color: IND_COLORS.bb_upper,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      sUpper.setData(bb.upper as any);
      indicatorSeriesRef.current.set("bb_upper", sUpper);

      const sMid = chart.addSeries(LineSeries, {
        color: IND_COLORS.bb_mid,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      sMid.setData(bb.mid as any);
      indicatorSeriesRef.current.set("bb_mid", sMid);

      const sLower = chart.addSeries(LineSeries, {
        color: IND_COLORS.bb_lower,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      sLower.setData(bb.lower as any);
      indicatorSeriesRef.current.set("bb_lower", sLower);
    }

    if (activeIndicators.has("vwap")) {
      const s = chart.addSeries(LineSeries, {
        color: IND_COLORS.vwap,
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      s.setData(calcVWAP(candles) as any);
      indicatorSeriesRef.current.set("vwap", s);
    }

    if (activeIndicators.has("vol")) {
      const s = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "vol",
      });
      chart.priceScale("vol").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      s.setData(
        candles.map((c) => ({
          time: c.time,
          value: c.volume,
          color: c.close >= c.open ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)",
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
        })) as any,
      );
      indicatorSeriesRef.current.set("vol", s);
    }
  }, [candles, activeIndicators]);

  // ─── Draw order lines + compute label groups (Task 1) ───
  const drawOrderLines = useCallback(
    (ordersToShow: GridOrder[]) => {
      const series = candleSeriesRef.current;
      if (!series) return;

      // Remove old price lines
      for (const line of priceLineRefs.current.values()) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        series.removePriceLine(line as any);
      }
      priceLineRefs.current.clear();

      const active = ordersToShow.filter((o) =>
        ["placed", "wait"].includes(o.status),
      );

      // Draw thin horizontal lines (no labels — labels are in overlay)
      for (const order of active) {
        const price = Number(order.price);
        const priceSell = Number(order.price_sell);
        const colors = ORDER_COLORS[order.status] ?? ORDER_COLORS.placed;

        const buyLine = series.createPriceLine({
          price,
          color: colors.buy,
          lineWidth: 1,
          lineStyle: order.status === "wait" ? LineStyle.Dotted : LineStyle.Solid,
          axisLabelVisible: false,
          title: "",
        });
        priceLineRefs.current.set(`buy-${order.id}`, buyLine);

        const sellLine = series.createPriceLine({
          price: priceSell,
          color: colors.sell,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: false,
          title: "",
        });
        priceLineRefs.current.set(`sell-${order.id}`, sellLine);
      }

      // Compute collision-aware label layout
      const priceScale = chartRef.current?.priceScale("right");
      if (!priceScale) return;

      const layoutOrders: OrderForLayout[] = active.map((o) => ({
        id: o.id,
        gridIndex: o.grid_index,
        side: o.side as "buy" | "sell",
        price: Number(o.price),
        priceSell: Number(o.price_sell),
        amount: Number(o.amount),
        status: o.status,
      }));

      // Use series.priceToCoordinate for accurate Y mapping
      const priceToY = (p: number): number => {
        const coord = series.priceToCoordinate(p);
        return coord ?? 0;
      };

      const groups = resolveOrderLabelLayout(layoutOrders, priceToY, 22);
      setLabelGroups(groups);
    },
    [symbol],
  );

  useEffect(() => {
    if (orders) drawOrderLines(orders);
  }, [orders, drawOrderLines]);

  // ─── Real-time ticker polling ───
  useEffect(() => {
    if (tickerIntervalRef.current) clearInterval(tickerIntervalRef.current);
    if (!symbol || !exchange) return;

    const poll = async () => {
      try {
        const ticker = await fetchTicker(exchange, symbol);
        setPrevPrice(lastPrice);
        setLastPrice(ticker.last);

        if (candleSeriesRef.current && candles?.length) {
          const lastCandle = candles[candles.length - 1];
          candleSeriesRef.current.update({
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            time: lastCandle.time as any,
            open: lastCandle.open,
            high: Math.max(lastCandle.high, ticker.last),
            low: Math.min(lastCandle.low, ticker.last),
            close: ticker.last,
          });
        }
      } catch { /* ignore */ }
    };

    void poll();
    tickerIntervalRef.current = setInterval(poll, 3000);
    return () => {
      if (tickerIntervalRef.current) clearInterval(tickerIntervalRef.current);
    };
  }, [exchange, symbol, candles]);

  // ─── Derived stats ───
  const activeOrders = orders?.filter((o) => ["placed", "wait"].includes(o.status)) ?? [];
  const placedOrders = activeOrders.filter((o) => o.status === "placed");
  const waitOrders = activeOrders.filter((o) => o.status === "wait");
  const buyOrders = activeOrders.filter((o) => o.side === "buy");
  const sellOrders = activeOrders.filter((o) => o.side === "sell");

  // Task 3: rounds completed (sell trades with positive profit)
  const roundsCompleted = useMemo(() => {
    const allOrders = orders ?? [];
    return allOrders.filter((o) => o.status === "filled" && o.side === "sell" && Number(o.profit) > 0).length;
  }, [orders]);

  // Task 2: filtered and sorted orders for table
  const tableOrders = useMemo(() => {
    const filtered = filterOrders(activeOrders, orderFilter);
    return sortOrders(filtered, orderSort);
  }, [activeOrders, orderFilter, orderSort]);

  const fp = (p: number) => formatPrice(p, symbol);

  const priceDirection =
    lastPrice && prevPrice
      ? lastPrice > prevPrice ? "up" : lastPrice < prevPrice ? "down" : "flat"
      : "flat";

  const priceRange = useMemo(() => {
    if (!activeOrders.length) return null;
    const prices = activeOrders.flatMap((o) => [Number(o.price), Number(o.price_sell)]);
    return { min: Math.min(...prices), max: Math.max(...prices) };
  }, [activeOrders]);

  const latestCandle = candles?.length ? candles[candles.length - 1] : null;
  const dailyChange = latestCandle ? latestCandle.close - latestCandle.open : 0;
  const dailyChangePct = latestCandle && latestCandle.open ? (dailyChange / latestCandle.open) * 100 : 0;

  return (
    <div className={`space-y-5 ${isFullscreen ? "fixed inset-0 z-50 bg-[#08111f] overflow-auto p-4" : ""}`}>
      {/* ─── Header ─── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">График</h1>
            <p className="mt-0.5 text-sm text-white/30">
              TradingView-стиль с индикаторами
            </p>
          </div>
          {/* Task 4: Density toggle */}
          <button
            onClick={toggleDensity}
            className={`ml-2 rounded-lg px-3 py-1.5 text-[11px] font-medium transition-all ${
              compact
                ? "bg-indigo-500/20 text-indigo-300 ring-1 ring-indigo-500/30"
                : "bg-white/[0.03] text-white/30 hover:text-white/60"
            }`}
            title={compact ? "Полный режим" : "Компактный режим"}
          >
            {compact ? "◫ Компакт" : "◫ Плотность"}
          </button>
        </div>

        {lastPrice && (
          <div className="flex items-center gap-5">
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-widest text-white/30 mb-0.5">{symbol}</div>
              <div className="flex items-baseline gap-2">
                <span
                  className={`text-3xl font-bold tabular-nums tracking-tight transition-colors duration-300 ${
                    priceDirection === "up" ? "text-emerald-400" : priceDirection === "down" ? "text-red-400" : "text-white"
                  }`}
                >
                  {fp(lastPrice)}
                </span>
                {latestCandle && (
                  <span className={`text-xs tabular-nums font-medium ${dailyChange >= 0 ? "text-emerald-400/70" : "text-red-400/70"}`}>
                    {dailyChange >= 0 ? "+" : ""}{fp(dailyChange)} ({dailyChangePct >= 0 ? "+" : ""}{dailyChangePct.toFixed(2)}%)
                  </span>
                )}
              </div>
            </div>
            <div className="h-10 w-px bg-white/[0.06]" />
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px]">
              <span className="text-white/30">На бирже</span>
              <span className="text-right tabular-nums text-emerald-400 font-medium">{placedOrders.length}</span>
              <span className="text-white/30">Ожидание</span>
              <span className="text-right tabular-nums text-amber-400 font-medium">{waitOrders.length}</span>
            </div>
          </div>
        )}
      </div>

      {/* ─── Grid selector + timeframe ─── */}
      <div className="flex flex-wrap items-center gap-2">
        {runningGrids.map((g) => {
          const isActive = selectedGridId === g.id;
          const pnl = Number(g.realized_pnl);
          return (
            <button
              key={g.id}
              onClick={() => setSelectedGridId(g.id)}
              className={`group flex items-center gap-2.5 rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
                isActive
                  ? "bg-white/[0.08] text-white ring-1 ring-white/10"
                  : "bg-white/[0.03] text-white/50 hover:bg-white/[0.06] hover:text-white/80"
              }`}
            >
              <span className={`inline-block h-2 w-2 rounded-full transition ${isActive ? "bg-emerald-400 shadow-sm shadow-emerald-400/50" : "bg-white/20"}`} />
              <span>{g.name}</span>
              <span className={`text-xs tabular-nums ${pnl >= 0 ? "text-emerald-400/70" : "text-red-400/70"}`}>
                {formatPnl(pnl)}
              </span>
            </button>
          );
        })}

        {runningGrids.length === 0 && (
          <div className="text-sm text-white/30">Нет запущенных сеток</div>
        )}

        <div className="ml-auto flex gap-0.5 rounded-xl bg-white/[0.04] p-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`rounded-lg px-3 py-1.5 text-[11px] font-medium transition-all ${
                timeframe === tf
                  ? "bg-indigo-500/80 text-white shadow-sm shadow-indigo-500/30"
                  : "text-white/40 hover:text-white/70"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Grid info strip (Task 3) ─── */}
      {selectedGrid && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 rounded-xl bg-white/[0.02] border border-white/[0.04] px-5 py-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="text-white/30">Стратегия</span>
            <span className="text-white/80 font-medium">{STRATEGY_LABELS[selectedGrid.strategy] ?? selectedGrid.strategy}</span>
          </div>
          <div className="h-3 w-px bg-white/[0.06]" />
          <div className="flex items-center gap-1.5">
            <span className="text-white/30">Шаг</span>
            <span className="text-white/80 font-medium tabular-nums">{selectedGrid.grid_step}</span>
          </div>
          <div className="h-3 w-px bg-white/[0.06]" />
          <div className="flex items-center gap-1.5">
            <span className="text-white/30">Профит</span>
            <span className="text-white/80 font-medium tabular-nums">{selectedGrid.profit_step}</span>
          </div>
          <div className="h-3 w-px bg-white/[0.06]" />
          <div className="flex items-center gap-1.5">
            <span className="text-white/30">Лот</span>
            <span className="text-white/80 font-medium tabular-nums">
              {selectedGrid.lot_quote ?? selectedGrid.lot_size} {selectedGrid.lot_quote ? symbol.split("/")[1] : symbol.split("/")[0]}
            </span>
          </div>
          {priceRange && (
            <>
              <div className="h-3 w-px bg-white/[0.06]" />
              <div className="flex items-center gap-1.5">
                <span className="text-white/30">Диапазон</span>
                <span className="text-white/80 font-medium tabular-nums">{fp(priceRange.min)} — {fp(priceRange.max)}</span>
              </div>
            </>
          )}
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-white/30">PnL</span>
            <span className={`font-semibold tabular-nums ${Number(selectedGrid.realized_pnl) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {formatPnl(Number(selectedGrid.realized_pnl))} USDT
            </span>
            <span className="text-white/20 ml-1">·</span>
            <span className="text-white/40 tabular-nums">{selectedGrid.total_trades} сделок</span>
          </div>
        </div>
      )}

      {/* ─── Indicators toolbar ─── */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] uppercase tracking-wider text-white/20 mr-1">Индикаторы</span>
        {INDICATORS.map((ind) => (
          <button
            key={ind.id}
            onClick={() => toggleIndicator(ind.id)}
            className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all ${
              activeIndicators.has(ind.id)
                ? "bg-white/10 text-white ring-1 ring-white/10"
                : "bg-white/[0.03] text-white/30 hover:text-white/60"
            }`}
          >
            {ind.label}
            {activeIndicators.has(ind.id) && ind.id !== "vol" && ind.id !== "bb" && ind.id !== "vwap" && (
              <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: IND_COLORS[ind.id] }} />
            )}
          </button>
        ))}

        <div className="ml-auto flex gap-1.5">
          <button
            onClick={() => chartRef.current?.timeScale().fitContent()}
            className="rounded-lg bg-white/[0.03] px-2.5 py-1 text-[11px] text-white/30 hover:text-white/60 transition"
            title="По размеру"
          >
            ⊞
          </button>
          <button
            onClick={() => setIsFullscreen((f) => !f)}
            className="rounded-lg bg-white/[0.03] px-2.5 py-1 text-[11px] text-white/30 hover:text-white/60 transition"
            title="Полный экран"
          >
            {isFullscreen ? "⊟" : "⊞"}
          </button>
        </div>
      </div>

      {/* ─── Chart with OHLCV overlay + order label overlay (Task 1) ─── */}
      <Card className="overflow-hidden p-0 border border-white/[0.04] relative">
        {/* OHLCV crosshair data */}
        <div className="absolute top-2 left-3 z-10 flex items-center gap-3 text-[11px] tabular-nums pointer-events-none">
          {crosshairData ? (
            <>
              <span className="text-white/40">{crosshairData.time}</span>
              <span className="text-white/30">O</span>
              <span className="text-white/70">{fp(crosshairData.open)}</span>
              <span className="text-white/30">H</span>
              <span className="text-white/70">{fp(crosshairData.high)}</span>
              <span className="text-white/30">L</span>
              <span className="text-white/70">{fp(crosshairData.low)}</span>
              <span className="text-white/30">C</span>
              <span className={crosshairData.change >= 0 ? "text-emerald-400" : "text-red-400"}>
                {fp(crosshairData.close)}
              </span>
              <span className={`${crosshairData.change >= 0 ? "text-emerald-400/60" : "text-red-400/60"}`}>
                {crosshairData.changePct >= 0 ? "+" : ""}{crosshairData.changePct.toFixed(2)}%
              </span>
            </>
          ) : latestCandle ? (
            <>
              <span className="text-white/30">O</span>
              <span className="text-white/50">{fp(latestCandle.open)}</span>
              <span className="text-white/30">H</span>
              <span className="text-white/50">{fp(latestCandle.high)}</span>
              <span className="text-white/30">L</span>
              <span className="text-white/50">{fp(latestCandle.low)}</span>
              <span className="text-white/30">C</span>
              <span className="text-white/50">{fp(latestCandle.close)}</span>
              <span className="text-white/30">Vol</span>
              <span className="text-white/50">{formatVol(latestCandle.volume)}</span>
            </>
          ) : null}
        </div>

        {/* Active indicator labels */}
        <div className="absolute top-2 right-3 z-10 flex items-center gap-2 text-[10px] pointer-events-none">
          {activeIndicators.has("ma7") && <span style={{ color: IND_COLORS.ma7 }}>MA(7)</span>}
          {activeIndicators.has("ma25") && <span style={{ color: IND_COLORS.ma25 }}>MA(25)</span>}
          {activeIndicators.has("ma99") && <span style={{ color: IND_COLORS.ma99 }}>MA(99)</span>}
          {activeIndicators.has("ema12") && <span style={{ color: IND_COLORS.ema12 }}>EMA(12)</span>}
          {activeIndicators.has("ema26") && <span style={{ color: IND_COLORS.ema26 }}>EMA(26)</span>}
          {activeIndicators.has("bb") && <span style={{ color: IND_COLORS.bb_mid }}>BB(20,2)</span>}
          {activeIndicators.has("vwap") && <span style={{ color: IND_COLORS.vwap }}>VWAP</span>}
        </div>

        {/* Order label overlay (Task 1) */}
        <OrderLabelOverlay
          groups={labelGroups}
          chartHeight={chartHeight}
          symbol={symbol}
        />

        <div ref={chartContainerRef} className="w-full" style={{ height: chartHeight }} />
      </Card>

      {/* ─── Order stats row (Task 3: added Кругов) ─── */}
      {selectedGrid && (
        <div className="grid gap-2 grid-cols-2 sm:grid-cols-6">
          {[
            { label: "Всего", value: activeOrders.length, color: "text-white" },
            { label: "Buy", value: buyOrders.length, color: "text-emerald-400" },
            { label: "Sell", value: sellOrders.length, color: "text-red-400" },
            { label: "На бирже", value: placedOrders.length, color: "text-indigo-400" },
            { label: "Ожидание", value: waitOrders.length, color: "text-amber-400" },
            { label: "Кругов", value: roundsCompleted, color: "text-cyan-400" },
          ].map(({ label, value, color }) => (
            <div key={label} className="flex items-center justify-between rounded-xl bg-white/[0.02] border border-white/[0.04] px-4 py-3">
              <span className="text-[11px] text-white/30 uppercase tracking-wider">{label}</span>
              <span className={`text-lg font-bold tabular-nums ${color}`}>{value}</span>
            </div>
          ))}
        </div>
      )}

      {/* ─── Active orders table (Task 2: ID, spread, filters, sort) ─── */}
      {activeOrders.length > 0 && (
        <Card className="border border-white/[0.04]">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold">Активные ордера</h2>
              <Badge tone="neutral">{activeOrders.length}</Badge>
            </div>
            <button
              onClick={() => setShowTable(!showTable)}
              className="text-[11px] text-white/30 hover:text-white/60 transition uppercase tracking-wider"
            >
              {showTable ? "Свернуть" : "Развернуть"}
            </button>
          </div>

          {compact && !showTable ? (
            /* Density mode: compact summary */
            <div className="flex items-center gap-4 text-xs text-white/40">
              <span>Buy: <span className="text-emerald-400 font-medium">{buyOrders.length}</span></span>
              <span>Sell: <span className="text-red-400 font-medium">{sellOrders.length}</span></span>
              <span>На бирже: <span className="text-indigo-400 font-medium">{placedOrders.length}</span></span>
              <span>Ожидание: <span className="text-amber-400 font-medium">{waitOrders.length}</span></span>
            </div>
          ) : showTable ? (
            <>
              {/* Filter chips (Task 2) */}
              <div className="flex flex-wrap items-center gap-1.5 mb-4">
                {FILTER_CHIPS.map((chip) => {
                  const isActive = orderFilter === chip.key;
                  return (
                    <button
                      key={chip.key}
                      onClick={() => setOrderFilter(chip.key)}
                      className={`rounded-lg px-3 py-1 text-[11px] font-medium transition-all ${
                        isActive
                          ? "bg-white/10 text-white ring-1 ring-white/10"
                          : "bg-white/[0.03] text-white/30 hover:text-white/60"
                      }`}
                    >
                      {chip.label}
                    </button>
                  );
                })}
                <div className="ml-auto flex items-center gap-1.5">
                  <span className="text-[10px] text-white/20">Сортировка:</span>
                  <button
                    onClick={() => setOrderSort((s) => (s === "index" ? "price" : "index"))}
                    className="rounded-lg bg-white/[0.03] px-2.5 py-1 text-[11px] text-white/40 hover:text-white/70 transition"
                  >
                    {orderSort === "index" ? "По индексу" : "По цене"}
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto -mx-4 px-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06] text-[10px] uppercase tracking-wider text-white/25">
                      <th className="pb-3 pr-3 text-left font-medium">ID</th>
                      <th className="pb-3 pr-3 text-left font-medium">#</th>
                      <th className="pb-3 pr-3 text-left font-medium">Тип</th>
                      <th className="pb-3 pr-3 text-right font-medium">Покупка</th>
                      <th className="pb-3 pr-3 text-right font-medium">Продажа</th>
                      <th className="pb-3 pr-3 text-right font-medium">Спред</th>
                      <th className="pb-3 pr-3 text-right font-medium">Объём</th>
                      <th className="pb-3 pr-3 text-center font-medium">Статус</th>
                      <th className="pb-3 text-right font-medium">Профит</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableOrders.map((o) => {
                      const pBuy = Number(o.price);
                      const pSell = Number(o.price_sell);
                      const spread = pSell - pBuy;
                      const isNearPrice = lastPrice && Math.abs(pBuy - lastPrice) < spread * 1.5;
                      const orderId = `${o.side === "buy" ? "B" : "S"}#${o.grid_index}`;
                      return (
                        <tr key={o.id} className={`border-b border-white/[0.02] transition ${isNearPrice ? "bg-white/[0.02]" : "hover:bg-white/[0.015]"}`}>
                          <td className="py-3 pr-3 text-xs font-mono text-white/50">{orderId}</td>
                          <td className="py-3 pr-3 text-white/20 tabular-nums text-xs">{o.grid_index}</td>
                          <td className="py-3 pr-3">
                            <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${o.side === "buy" ? "text-emerald-400" : "text-red-400"}`}>
                              <span className={`inline-block h-1.5 w-1.5 rounded-full ${o.side === "buy" ? "bg-emerald-400" : "bg-red-400"}`} />
                              {o.side === "buy" ? "BUY" : "SELL"}
                            </span>
                          </td>
                          <td className="py-3 pr-3 text-right font-mono tabular-nums text-white/70">{fp(pBuy)}</td>
                          <td className="py-3 pr-3 text-right font-mono tabular-nums text-white/70">{fp(pSell)}</td>
                          <td className="py-3 pr-3 text-right font-mono tabular-nums text-white/20 text-xs">{fp(spread)}</td>
                          <td className="py-3 pr-3 text-right font-mono tabular-nums text-white/50 text-xs">{Number(o.amount).toFixed(6)}</td>
                          <td className="py-3 pr-3 text-center">
                            <Badge tone={o.status === "placed" ? "good" : o.status === "wait" ? "warn" : "neutral"}>
                              {o.status === "placed" ? "На бирже" : o.status === "wait" ? "Ожидание" : o.status}
                            </Badge>
                          </td>
                          <td className={`py-3 text-right font-mono tabular-nums text-xs ${Number(o.profit) > 0 ? "text-emerald-400" : Number(o.profit) < 0 ? "text-red-400" : "text-white/15"}`}>
                            {Number(o.profit) !== 0 ? formatPnl(Number(o.profit)) : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </Card>
      )}

      {/* ─── Filled trades per grid ─── */}
      {allGridTrades.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold tracking-tight">Исполненные сделки</h2>
          {allGridTrades.map(({ grid: g, trades, totalProfit, sellCount }) => {
            const gfp = (p: number) => formatPrice(p, g.symbol);
            const visibleTrades = trades.slice(0, tradesLimit);
            const hasMore = trades.length > tradesLimit;

            return (
              <Card key={g.id} className="border border-white/[0.04]">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />
                    <span className="font-semibold">{g.name}</span>
                    <span className="text-xs text-white/30">{g.symbol}</span>
                    <div className="h-3 w-px bg-white/[0.06]" />
                    <span className="text-xs text-white/30">{STRATEGY_LABELS[g.strategy] ?? g.strategy}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-3 text-xs">
                      <div className="text-white/30">Сделок <span className="text-white/60 font-medium tabular-nums">{trades.length}</span></div>
                      <div className="text-white/30">Кругов <span className="text-white/60 font-medium tabular-nums">{sellCount}</span></div>
                    </div>
                    <div className={`text-sm font-mono font-semibold tabular-nums ${totalProfit >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {formatPnl(totalProfit)} USDT
                    </div>
                  </div>
                </div>

                {/* Density mode: hide table in compact, show summary */}
                {compact ? (
                  <div className="flex items-center gap-4 text-xs text-white/40">
                    <span>Сделок: <span className="text-white/60 font-medium">{trades.length}</span></span>
                    <span>Кругов: <span className="text-white/60 font-medium">{sellCount}</span></span>
                    <span className={`font-mono font-medium ${totalProfit >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {formatPnl(totalProfit)} USDT
                    </span>
                  </div>
                ) : (
                  <>
                    <div className="overflow-x-auto -mx-4 px-4">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-white/[0.06] text-[10px] uppercase tracking-wider text-white/25">
                            <th className="pb-3 pr-3 text-left font-medium">ID</th>
                            <th className="pb-3 pr-3 text-left font-medium">#</th>
                            <th className="pb-3 pr-3 text-left font-medium">Тип</th>
                            <th className="pb-3 pr-3 text-right font-medium">Покупка</th>
                            <th className="pb-3 pr-3 text-right font-medium">Продажа</th>
                            <th className="pb-3 pr-3 text-right font-medium">Объём</th>
                            <th className="pb-3 pr-3 text-left font-medium">Исполнен</th>
                            <th className="pb-3 pr-3 text-right font-medium">Длит.</th>
                            <th className="pb-3 text-right font-medium">Профит</th>
                          </tr>
                        </thead>
                        <tbody>
                          {visibleTrades.map((o) => {
                            const pBuy = Number(o.price);
                            const pSell = Number(o.price_sell);
                            const profit = Number(o.profit);
                            const createdMs = new Date(o.created_at).getTime();
                            const filledMs = o.filled_at ? new Date(o.filled_at).getTime() : null;
                            const durationStr = filledMs ? formatDuration(filledMs - createdMs) : "—";
                            const tradeId = `${o.side === "buy" ? "B" : "S"}#${o.grid_index}`;
                            return (
                              <tr key={o.id} className="border-b border-white/[0.02] hover:bg-white/[0.015] transition">
                                <td className="py-2.5 pr-3 text-xs font-mono text-white/50">{tradeId}</td>
                                <td className="py-2.5 pr-3 text-white/20 tabular-nums text-xs">{o.grid_index}</td>
                                <td className="py-2.5 pr-3">
                                  <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${o.side === "buy" ? "text-emerald-400" : "text-red-400"}`}>
                                    <span className={`inline-block h-1.5 w-1.5 rounded-full ${o.side === "buy" ? "bg-emerald-400" : "bg-red-400"}`} />
                                    {o.side === "buy" ? "BUY" : "SELL"}
                                  </span>
                                </td>
                                <td className="py-2.5 pr-3 text-right font-mono tabular-nums text-white/70">{gfp(pBuy)}</td>
                                <td className="py-2.5 pr-3 text-right font-mono tabular-nums text-white/70">{gfp(pSell)}</td>
                                <td className="py-2.5 pr-3 text-right font-mono tabular-nums text-white/40 text-xs">{Number(o.amount).toFixed(6)}</td>
                                <td className="py-2.5 pr-3 text-white/40 text-xs tabular-nums">{o.filled_at ? formatRu(o.filled_at) : "—"}</td>
                                <td className="py-2.5 pr-3 text-right text-xs text-white/25 tabular-nums">{durationStr}</td>
                                <td className={`py-2.5 text-right font-mono tabular-nums text-xs font-medium ${profit > 0 ? "text-emerald-400" : profit < 0 ? "text-red-400" : "text-white/15"}`}>
                                  {profit !== 0 ? formatPnl(profit) : "—"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    {hasMore && (
                      <button
                        onClick={() => setTradesLimit((l) => l + 50)}
                        className="mt-3 w-full rounded-lg bg-white/[0.03] py-2 text-xs text-white/30 hover:bg-white/[0.06] hover:text-white/50 transition"
                      >
                        Показать ещё ({trades.length - tradesLimit} скрыто)
                      </button>
                    )}
                  </>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
