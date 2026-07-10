import { DndContext, closestCenter, PointerSensor, TouchSensor, useSensor, useSensors } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy, arrayMove } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  ArrowLeftRight,
  BarChart3,
  ChevronDown,
  Clock,
  DollarSign,
  Filter,
  GripVertical,
  Percent,
  RefreshCw,
  RotateCcw,
  Settings,
  Square,
  TrendingDown,
  TrendingUp,
  OctagonX,
  X,
  Zap,
} from "lucide-react";
import type { ComponentType, ReactNode } from "react";
import { Fragment, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { botEmergencyStop, botRestart, botStopAll, fetchBotStatus } from "../api/bot";
import { fetchAnalytics, fetchBalances, fetchDashboard } from "../api/dashboard";
import type {
  AccountBalance,
  CurrencyBalance,
  DailyActivity,
  DashboardData,
  DrawdownPoint,
  GridAnalytics,
  GridComparison,
  GridPnlSeries,
  HourlyDistribution,
  PeriodStats,
  PnlPoint,
  PositionSummary,
  RecentTrade,
  StrategyStats,
} from "../api/dashboard";
import { listGridOrders } from "../api/grids";
import type { GridOrder } from "../api/types";
import { useAuthStore } from "../store/auth";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { ConvertModal } from "../components/ConvertModal";

// ─── Helpers ───
const STRATEGY_LABELS: Record<string, string> = {
  simple: "Простая",
  capitalization: "Капитализация",
  reverse: "Реверс",
  reverse_cap: "Реверс+Кап",
  adaptive: "Адаптивная",
  adaptive_cap: "Адаптивная+Кап",
};

const STRATEGY_COLORS = ["#818cf8", "#34d399", "#fbbf24", "#f87171", "#38bdf8", "#a78bfa"];
const GRID_COLORS = ["#818cf8", "#34d399", "#fbbf24", "#f87171", "#38bdf8", "#a78bfa", "#fb923c", "#22d3ee"];

function formatPnl(value: number) {
  const sign = value >= 0 ? "+" : "";
  const abs = Math.abs(value);
  const decimals = abs > 0 && abs < 0.01 ? 8 : abs < 1 ? 4 : 2;
  const formatted = value.toFixed(decimals).replace(/0+$/, "").replace(/\.$/, "");
  return `${sign}${formatted}`;
}

const tooltipStyle = {
  background: "rgba(15,23,42,0.95)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 12,
  color: "#fff",
  fontSize: 12,
};

// ─── Grid Selector ───
function GridSelector({
  grids,
  selected,
  onSelect,
}: {
  grids: { grid_id: string; grid_name: string; symbol: string }[];
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Filter size={14} className="text-white/40" />
      <button
        onClick={() => onSelect(null)}
        className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${
          selected === null
            ? "bg-indigo-500/20 text-indigo-300 border border-indigo-400/30"
            : "bg-white/5 text-white/60 hover:bg-white/10"
        }`}
      >
        Все сетки
      </button>
      {grids.map((g) => (
        <button
          key={g.grid_id}
          onClick={() => onSelect(g.grid_id)}
          className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${
            selected === g.grid_id
              ? "bg-indigo-500/20 text-indigo-300 border border-indigo-400/30"
              : "bg-white/5 text-white/60 hover:bg-white/10"
          }`}
        >
          {g.grid_name} <span className="text-white/30">{g.symbol}</span>
        </button>
      ))}
    </div>
  );
}

// ─── MetricCard ───
function MetricCard({
  label,
  value,
  icon: Icon,
  trend,
  subtitle,
}: {
  label: string;
  value: string;
  icon: ComponentType<any>;
  trend?: "up" | "down" | "neutral";
  subtitle?: string;
}) {
  return (
    <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4 flex items-start gap-2 sm:gap-3">
      <div className="flex h-8 w-8 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-lg sm:rounded-xl bg-indigo-500/15">
        <Icon size={18} className="text-indigo-400" />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] sm:text-xs text-white/50 leading-tight">{label}</div>
        <div className="mt-0.5 text-sm sm:text-xl font-bold tracking-tight break-words">
          {value}
          {trend && trend !== "neutral" && (
            <span className={`ml-1.5 inline-flex text-xs ${trend === "up" ? "text-emerald-400" : "text-red-400"}`}>
              {trend === "up" ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            </span>
          )}
        </div>
        {subtitle && <div className="mt-0.5 text-[10px] text-white/40">{subtitle}</div>}
      </div>
    </div>
  );
}

// ─── EquityChart ───
function EquityChart({ data }: { data: DashboardData["equity_curve"] }) {
  if (data.length === 0) return <div className="flex h-48 items-center justify-center text-sm text-white/40">Нет данных</div>;
  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={data} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#818cf8" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#818cf8" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="label" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={40} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area type="monotone" dataKey="value" stroke="#818cf8" strokeWidth={2} fill="url(#equityGrad)" name="PnL" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── AllocationChart ───
function AllocationChart({ strategies }: { strategies: StrategyStats[] }) {
  const data = strategies.filter((s) => s.grids_count > 0);
  if (data.length === 0) return <div className="flex h-48 items-center justify-center text-sm text-white/40">Нет стратегий</div>;
  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width={160} height={160}>
        <PieChart>
          <Pie data={data} dataKey="grids_count" nameKey="strategy" cx="50%" cy="50%" innerRadius={40} outerRadius={68} paddingAngle={3} stroke="none">
            {data.map((s, i) => (
              <Cell key={s.strategy} fill={STRATEGY_COLORS[i % STRATEGY_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
      <div className="space-y-1.5 text-xs">
        {data.map((s, i) => (
          <div key={s.strategy} className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: STRATEGY_COLORS[i % STRATEGY_COLORS.length] }} />
            <span className="text-white/70">{STRATEGY_LABELS[s.strategy] || s.strategy}</span>
            <span className="font-medium">{s.grids_count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── StrategiesPanel ───
function StrategiesPanel({ strategies }: { strategies: StrategyStats[] }) {
  if (strategies.length === 0) return <div className="text-sm text-white/40">Нет стратегий</div>;
  return (
    <div className="space-y-3">
      {strategies.map((s) => (
        <div key={s.strategy} className="flex items-center justify-between rounded-xl bg-white/5 p-2.5 sm:p-3">
          <div>
            <div className="text-sm font-medium">{STRATEGY_LABELS[s.strategy] || s.strategy}</div>
            <div className="mt-0.5 text-xs text-white/50">
              {s.grids_count} сеток · {s.active_count} активных · {s.total_trades} трейдов
            </div>
          </div>
          <div className={`text-sm font-semibold ${s.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {formatPnl(s.total_pnl)} USDT
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── PositionsTable ───
const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: "Ожидает",
  placed: "На бирже",
  filled: "Исполнен",
  cancelled: "Отменён",
  wait: "Ожидание",
  error: "Ошибка",
};

function PositionsTable({ positions }: { positions: PositionSummary[] }) {
  const [expandedGrid, setExpandedGrid] = useState<string | null>(null);
  const [orders, setOrders] = useState<GridOrder[]>([]);
  const [loadingOrders, setLoadingOrders] = useState(false);

  const toggleGrid = async (gridId: string) => {
    if (expandedGrid === gridId) { setExpandedGrid(null); return; }
    setExpandedGrid(gridId);
    setLoadingOrders(true);
    try {
      const data = await listGridOrders(gridId);
      setOrders(data.filter((o) => ["placed", "pending", "wait"].includes(o.status)));
    } catch { setOrders([]); } finally { setLoadingOrders(false); }
  };

  if (positions.length === 0) return <div className="text-sm text-white/40">Нет позиций</div>;
  return (
    <div className="overflow-x-auto no-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0">
      <table className="min-w-[600px] w-full text-left text-xs sm:text-sm">
        <thead>
          <tr className="border-b border-white/10 text-xs uppercase tracking-wider text-white/40">
            <th className="pb-2 pr-4 w-6"></th>
            <th className="pb-2 pr-4">Сетка</th>
            <th className="pb-2 pr-4">Пара</th>
            <th className="pb-2 pr-4">Стратегия</th>
            <th className="pb-2 pr-4">Статус</th>
            <th className="pb-2 pr-4">Уровни</th>
            <th className="pb-2 pr-4">Трейды</th>
            <th className="pb-2 text-right">Чистая PnL</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {positions.map((p) => {
            const isExpanded = expandedGrid === p.grid_id;
            return (
              <Fragment key={p.grid_id}>
                <tr className="text-white/80 transition hover:bg-white/5 cursor-pointer" onClick={() => toggleGrid(p.grid_id)}>
                  <td className="py-2.5 pr-2">
                    <ChevronDown size={14} className={`text-white/40 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                  </td>
                  <td className="py-2.5 pr-4 font-medium text-white">{p.grid_name}</td>
                  <td className="py-2.5 pr-4">{p.symbol}</td>
                  <td className="py-2.5 pr-4">{STRATEGY_LABELS[p.strategy] || p.strategy}</td>
                  <td className="py-2.5 pr-4">
                    <Badge tone={p.status === "running" ? "good" : p.status === "error" ? "warn" : "neutral"}>{p.status}</Badge>
                  </td>
                  <td className="py-2.5 pr-4">{p.filled_orders}/{p.current_levels}</td>
                  <td className="py-2.5 pr-4">{p.total_trades}</td>
                  <td className="py-2.5 text-right">
                    <div className={`font-semibold ${p.realized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {formatPnl(p.realized_pnl)} USDT
                    </div>
                    {p.auto_convert_to && p.unconverted_pnl > 0 && (
                      <div className="mt-0.5 text-[10px] text-amber-300/80">
                        {p.unconverted_pnl.toFixed(4)} USDT &rarr; {p.auto_convert_to}
                      </div>
                    )}
                  </td>
                </tr>
                {isExpanded && (
                  <tr>
                    <td colSpan={8} className="p-0">
                      <div className="bg-white/[0.02] px-4 py-3">
                        {loadingOrders ? (
                          <div className="flex items-center gap-2 text-xs text-white/40">
                            <div className="h-3 w-3 animate-spin rounded-full border border-indigo-400 border-t-transparent" /> Загрузка...
                          </div>
                        ) : orders.length === 0 ? (
                          <div className="text-xs text-white/40">Нет активных ордеров</div>
                        ) : (
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="text-white/30 uppercase tracking-wider">
                                <th className="pb-1.5 pr-3 text-left">#</th>
                                <th className="pb-1.5 pr-3 text-left">Сторона</th>
                                <th className="pb-1.5 pr-3 text-right">Цена покупки</th>
                                <th className="pb-1.5 pr-3 text-right">Цена продажи</th>
                                <th className="pb-1.5 pr-3 text-right">Объём</th>
                                <th className="pb-1.5 pr-3 text-left">Статус</th>
                                <th className="pb-1.5 text-right">Профит</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                              {orders.map((o) => (
                                <tr key={o.id} className="text-white/70">
                                  <td className="py-1.5 pr-3 text-white/40">{o.grid_index}</td>
                                  <td className="py-1.5 pr-3">
                                    <span className={o.side === "buy" ? "text-emerald-400" : "text-red-400"}>{o.side === "buy" ? "BUY" : "SELL"}</span>
                                  </td>
                                  <td className="py-1.5 pr-3 text-right font-mono">{Number(o.price).toFixed(4)}</td>
                                  <td className="py-1.5 pr-3 text-right font-mono">{Number(o.price_sell).toFixed(4)}</td>
                                  <td className="py-1.5 pr-3 text-right font-mono">{Number(o.amount).toFixed(6)}</td>
                                  <td className="py-1.5 pr-3">
                                    <Badge tone={o.status === "placed" ? "good" : o.status === "wait" ? "warn" : "neutral"}>
                                      {ORDER_STATUS_LABELS[o.status] || o.status}
                                    </Badge>
                                  </td>
                                  <td className={`py-1.5 text-right font-mono ${Number(o.profit) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                    {Number(o.profit) !== 0 ? formatPnl(Number(o.profit)) : "\u2014"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── BalancesPanel ───
function BalancesPanel({ balances }: { balances: AccountBalance[] }) {
  const [convertAccountId, setConvertAccountId] = useState<string | null>(null);
  const [convertCurrencies, setConvertCurrencies] = useState<CurrencyBalance[]>([]);

  if (balances.length === 0) return <div className="text-sm text-white/40">Нет подключённых аккаунтов</div>;
  return (
    <>
      <div className="space-y-3">
        {balances.map((b) => (
          <div key={b.account_id} className="rounded-xl bg-white/5 p-3 sm:p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="text-xs sm:text-sm font-medium truncate">{b.name}</div>
                <div className="mt-0.5 text-[10px] sm:text-xs text-white/50">{b.exchange}{b.testnet ? " (testnet)" : ""}</div>
              </div>
              <div className="shrink-0 flex items-center gap-2">
                {!b.error && (
                  <button
                    onClick={() => { setConvertAccountId(b.account_id); setConvertCurrencies(b.currencies); }}
                    className="flex items-center gap-1 rounded-lg border border-indigo-400/20 bg-indigo-400/10 px-2 py-1 text-[10px] sm:text-xs font-medium text-indigo-300 hover:bg-indigo-400/20 transition"
                  >
                    <ArrowLeftRight size={10} /> Конверт.
                  </button>
                )}
                {b.error && <div className="text-xs text-red-400">{b.error}</div>}
              </div>
            </div>
            {!b.error && b.currencies.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {b.currencies.map((c) => {
                  const total = Number(c.total);
                  const free = Number(c.free);
                  const used = Number(c.used);
                  const isStable = ["USDT", "USDC", "BUSD", "DAI", "TUSD"].includes(c.currency);
                  const decimals = isStable ? 2 : total < 1 ? 6 : total < 100 ? 4 : 2;
                  return (
                    <div key={c.currency} className="flex items-center justify-between gap-2 rounded-lg bg-white/5 px-2.5 py-1.5 sm:px-3 sm:py-2">
                      <div className="text-xs sm:text-sm font-medium text-white/90">{c.currency}</div>
                      <div className="text-right min-w-0">
                        <div className="text-xs sm:text-sm font-semibold text-emerald-400">{total.toFixed(decimals)}</div>
                        <div className="text-[9px] sm:text-[10px] text-white/40 truncate">
                          {free.toFixed(decimals)} св. · {used.toFixed(decimals)} орд.
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {!b.error && b.currencies.length === 0 && <div className="mt-2 text-xs text-white/40">Кошелёк пуст</div>}
          </div>
        ))}
      </div>
      <ConvertModal open={!!convertAccountId} onClose={() => setConvertAccountId(null)} accountId={convertAccountId || ""} currencies={convertCurrencies} />
    </>
  );
}

// ─── Analytics Charts ───

function PnlTimelineChart({ series }: { series: GridPnlSeries[] }) {
  if (series.length === 0) return <div className="flex h-48 items-center justify-center text-sm text-white/40">Нет данных о сделках</div>;
  const allDates = new Set<string>();
  for (const s of series) for (const p of s.points) allDates.add(p.date.slice(0, 10));
  const dates = [...allDates].sort();
  const chartData = dates.map((date) => {
    const row: Record<string, string | number> = { date: date.slice(5) };
    for (const s of series) {
      const pts = s.points.filter((p) => p.date.slice(0, 10) <= date);
      row[s.grid_name] = pts.length > 0 ? pts[pts.length - 1].cumulative : 0;
    }
    return row;
  });
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
        <XAxis dataKey="date" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={40} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 11, color: "rgba(255,255,255,0.6)" }} />
        {series.map((s, i) => (
          <Line key={s.grid_id} type="monotone" dataKey={s.grid_name} stroke={GRID_COLORS[i % GRID_COLORS.length]} strokeWidth={2} dot={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function GridPnlChart({ points }: { points: PnlPoint[] }) {
  if (points.length === 0) return <div className="flex h-48 items-center justify-center text-sm text-white/40">Нет данных</div>;
  const chartData = points.map((p, i) => ({ idx: i, date: p.date.slice(5, 16), cumulative: p.cumulative, pnl: p.pnl }));
  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
        <defs>
          <linearGradient id="gridPnlGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#34d399" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="date" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={40} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area type="monotone" dataKey="cumulative" stroke="#34d399" strokeWidth={2} fill="url(#gridPnlGrad)" name="Кумул. PnL" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function TradeActivityChart({ data }: { data: DailyActivity[] }) {
  if (data.length === 0) return <div className="flex h-48 items-center justify-center text-sm text-white/40">Нет данных</div>;
  const chartData = data.map((d) => ({ ...d, date: d.date.slice(5) }));
  return (
    <ResponsiveContainer width="100%" height={170}>
      <BarChart data={chartData} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
        <XAxis dataKey="date" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={30} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="buys" name="Покупки" fill="#34d399" radius={[4, 4, 0, 0]} />
        <Bar dataKey="sells" name="Продажи" fill="#818cf8" radius={[4, 4, 0, 0]} />
        <Legend wrapperStyle={{ fontSize: 10, color: "rgba(255,255,255,0.6)" }} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function PeriodStatsPanel({ stats }: { stats: PeriodStats }) {
  const rows = [
    { label: "За 24 часа", pnl: stats.pnl_24h, trades: stats.trades_24h },
    { label: "Сегодня", pnl: stats.pnl_today, trades: stats.trades_today },
    { label: "За 7 дней", pnl: stats.pnl_week, trades: stats.trades_week },
    { label: "За 30 дней", pnl: stats.pnl_month, trades: stats.trades_month },
  ];
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between rounded-xl bg-white/5 p-2.5 sm:p-3">
            <div className="text-sm text-white/70">{r.label}</div>
            <div className="text-right">
              <div className={`text-sm font-semibold ${r.pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {formatPnl(r.pnl)} USDT
              </div>
              <div className="text-xs text-white/40">{r.trades} сделок</div>
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-emerald-400/10 p-2.5 sm:p-3 text-center">
          <div className="text-xs text-emerald-300/70">Заработано (чистая)</div>
          <div className="mt-1 text-sm font-semibold text-emerald-400">{formatPnl(stats.total_profit)} USDT</div>
        </div>
        <div className="rounded-xl bg-red-400/10 p-2.5 sm:p-3 text-center">
          <div className="text-xs text-red-300/70">Потеряно</div>
          <div className="mt-1 text-sm font-semibold text-red-400">{formatPnl(stats.total_loss)} USDT</div>
        </div>
        <div className="rounded-xl bg-amber-400/10 p-2.5 sm:p-3 text-center">
          <div className="text-xs text-amber-300/70">Комиссия биржи</div>
          <div className="mt-1 text-sm font-semibold text-amber-400">{formatPnl(-stats.total_commission)} USDT</div>
        </div>
        <div className="rounded-xl bg-indigo-400/10 p-2.5 sm:p-3 text-center">
          <div className="text-xs text-indigo-300/70">Кругов (циклов)</div>
          <div className="mt-1 text-sm font-semibold text-indigo-400">{stats.total_rounds}</div>
        </div>
        <div className="rounded-xl bg-emerald-400/10 p-2.5 sm:p-3 text-center">
          <div className="text-xs text-emerald-300/70">Лучшая сделка</div>
          <div className="mt-1 text-sm font-semibold text-emerald-400">{formatPnl(stats.best_trade)} USDT</div>
        </div>
        <div className="rounded-xl bg-red-400/10 p-2.5 sm:p-3 text-center">
          <div className="text-xs text-red-300/70">Худшая сделка</div>
          <div className="mt-1 text-sm font-semibold text-red-400">{formatPnl(stats.worst_trade)} USDT</div>
        </div>
      </div>
    </div>
  );
}

function RecentTradesFeed({ trades }: { trades: RecentTrade[] }) {
  if (trades.length === 0) return <div className="text-sm text-white/40">Нет сделок</div>;
  return (
    <div className="space-y-2">
      {trades.map((t, i) => {
        const isBuy = t.side === "buy";
        const time = new Date(t.created_at).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
        return (
          <div key={`${t.created_at}-${t.grid_name}-${i}`} className="flex items-center justify-between gap-2 rounded-xl bg-white/5 p-2.5 sm:p-3">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <div className={`flex h-7 w-7 sm:h-8 sm:w-8 shrink-0 items-center justify-center rounded-lg text-[10px] sm:text-xs font-bold ${isBuy ? "bg-emerald-400/15 text-emerald-400" : "bg-indigo-400/15 text-indigo-400"}`}>
                {isBuy ? "B" : "S"}
              </div>
              <div className="min-w-0">
                <div className="text-xs sm:text-sm truncate">
                  <span className="font-medium">{isBuy ? "Куплено" : "Продано"}</span>
                  {t.amount != null && <span className="text-white/60"> {t.amount}</span>}
                  <span className="text-white/40"> {t.symbol}</span>
                  {t.price != null && <span className="text-white/50"> @ {t.price}</span>}
                </div>
                <div className="text-[10px] sm:text-xs text-white/40 truncate">
                  {t.grid_name} · {time}
                  {t.commission != null && t.commission > 0 && (
                    <span className="text-amber-400/60"> · fee: {t.commission.toFixed(4)}</span>
                  )}
                </div>
              </div>
            </div>
            {t.pnl_delta != null && t.pnl_delta !== 0 && (
              <div className={`shrink-0 text-xs sm:text-sm font-semibold ${t.pnl_delta >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {formatPnl(t.pnl_delta)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Extended Analytics Components ───

function ExtendedMetrics({ stats }: { stats: PeriodStats }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div className="rounded-xl bg-white/5 p-2.5 sm:p-3 text-center">
        <div className="text-xs text-white/40">Win Rate</div>
        <div className="mt-1 text-lg font-bold text-emerald-400">{stats.win_rate}%</div>
      </div>
      <div className="rounded-xl bg-white/5 p-2.5 sm:p-3 text-center">
        <div className="text-xs text-white/40">Profit Factor</div>
        <div className={`mt-1 text-lg font-bold ${stats.profit_factor >= 1 ? "text-emerald-400" : "text-red-400"}`}>
          {stats.profit_factor >= 999 ? "\u221e" : stats.profit_factor.toFixed(2)}
        </div>
      </div>
      <div className="rounded-xl bg-white/5 p-2.5 sm:p-3 text-center">
        <div className="text-xs text-white/40">Макс. просадка</div>
        <div className="mt-1 text-lg font-bold text-red-400">{formatPnl(stats.max_drawdown)} USDT</div>
      </div>
      <div className="rounded-xl bg-white/5 p-2.5 sm:p-3 text-center">
        <div className="text-xs text-white/40">Объём торгов</div>
        <div className="mt-1 text-lg font-bold">${stats.total_volume.toFixed(0)}</div>
      </div>
      <div className="rounded-xl bg-white/5 p-2.5 sm:p-3 text-center">
        <div className="text-xs text-white/40">Ср. профит/сделку</div>
        <div className={`mt-1 text-sm font-semibold ${stats.avg_trade_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
          {formatPnl(stats.avg_trade_pnl)} USDT
        </div>
      </div>
      <div className="rounded-xl bg-white/5 p-2.5 sm:p-3 text-center">
        <div className="text-xs text-white/40">Ср. прибыльная</div>
        <div className="mt-1 text-sm font-semibold text-emerald-400">{formatPnl(stats.avg_profit_per_trade)} USDT</div>
      </div>
      <div className="rounded-xl bg-emerald-400/10 p-2.5 sm:p-3 text-center">
        <div className="text-xs text-emerald-300/70">Серия побед</div>
        <div className="mt-1 text-sm font-semibold">{stats.win_streak} / макс {stats.max_win_streak}</div>
      </div>
      <div className="rounded-xl bg-red-400/10 p-2.5 sm:p-3 text-center">
        <div className="text-xs text-red-300/70">Серия проигрышей</div>
        <div className="mt-1 text-sm font-semibold">{stats.loss_streak} / макс {stats.max_loss_streak}</div>
      </div>
    </div>
  );
}

function DrawdownChart({ data }: { data: DrawdownPoint[] }) {
  if (data.length === 0) return <div className="flex h-48 items-center justify-center text-sm text-white/40">Нет данных</div>;
  const chartData = data.map((d, i) => ({ idx: i, drawdown: d.drawdown, peak: d.peak }));
  return (
    <ResponsiveContainer width="100%" height={170}>
      <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
        <XAxis dataKey="idx" tick={false} axisLine={false} />
        <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={40} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area type="monotone" dataKey="drawdown" stroke="#f87171" fill="rgba(248,113,113,0.15)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function HourlyChart({ data }: { data: HourlyDistribution[] }) {
  if (data.every((d) => d.trades === 0)) return <div className="flex h-48 items-center justify-center text-sm text-white/40">Нет данных</div>;
  const chartData = data.map((d) => ({ ...d, label: `${String(d.hour).padStart(2, "0")}:00` }));
  return (
    <ResponsiveContainer width="100%" height={170}>
      <BarChart data={chartData} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
        <XAxis dataKey="label" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 9 }} axisLine={false} tickLine={false} interval={3} />
        <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={25} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="trades" name="Сделки" fill="#818cf8" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function GridComparisonTable({ grids }: { grids: GridComparison[] }) {
  if (grids.length === 0) return <div className="text-sm text-white/40">Нет данных для сравнения</div>;
  return (
    <div className="overflow-x-auto no-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0">
      <table className="min-w-[700px] w-full text-xs sm:text-sm">
        <thead className="bg-secondary text-left">
          <tr>
            <th className="px-3 py-2">Сетка</th>
            <th className="px-3 py-2">Стратегия</th>
            <th className="px-3 py-2 text-right">Сделки</th>
            <th className="px-3 py-2 text-right">Кругов</th>
            <th className="px-3 py-2 text-right">Чистая PnL</th>
            <th className="px-3 py-2 text-right">Комиссия</th>
            <th className="px-3 py-2 text-right">PnL/час</th>
            <th className="px-3 py-2 text-right">Win%</th>
            <th className="px-3 py-2 text-right">PF</th>
            <th className="px-3 py-2 text-right">Просадка</th>
            <th className="px-3 py-2 text-right">Объём</th>
            <th className="px-3 py-2 text-right">Часы</th>
          </tr>
        </thead>
        <tbody>
          {grids.map((g) => (
            <tr key={g.grid_id} className="border-t border-secondary">
              <td className="px-3 py-2">
                <div className="font-medium">{g.grid_name}</div>
                <div className="text-xs text-white/40">{g.symbol}</div>
              </td>
              <td className="px-3 py-2">{STRATEGY_LABELS[g.strategy] || g.strategy}</td>
              <td className="px-3 py-2 text-right">{g.total_trades}</td>
              <td className="px-3 py-2 text-right text-indigo-400">{g.total_rounds}</td>
              <td className={`px-3 py-2 text-right font-semibold ${g.realized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {formatPnl(g.realized_pnl)} USDT
              </td>
              <td className="px-3 py-2 text-right text-amber-400">{formatPnl(-g.total_commission)}</td>
              <td className={`px-3 py-2 text-right ${g.pnl_per_hour >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {formatPnl(g.pnl_per_hour)}
              </td>
              <td className="px-3 py-2 text-right">{g.win_rate}%</td>
              <td className="px-3 py-2 text-right">{g.profit_factor >= 999 ? "\u221e" : g.profit_factor.toFixed(2)}</td>
              <td className="px-3 py-2 text-right text-red-400">{formatPnl(g.max_drawdown)}</td>
              <td className="px-3 py-2 text-right">${g.total_volume.toFixed(0)}</td>
              <td className="px-3 py-2 text-right">{g.runtime_hours.toFixed(0)}ч</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Per-Grid PnL Cards (always visible) ───
function GridPnlCards({ grids }: { grids: GridAnalytics[] }) {
  if (grids.length === 0) return null;
  return (
    <div className="space-y-3">
      {grids.map((g, i) => {
        const s = g.period_stats;
        const color = GRID_COLORS[i % GRID_COLORS.length];
        return (
          <div key={g.grid_id} className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 min-w-0">
                <div className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: color }} />
                <div className="min-w-0">
                  <div className="text-sm font-semibold truncate">{g.grid_name}</div>
                  <div className="text-[10px] text-white/40">{g.symbol} · {STRATEGY_LABELS[g.strategy] || g.strategy} · {g.status === "running" ? "Работает" : "Остановлена"}</div>
                </div>
              </div>
              <div className={`shrink-0 text-lg sm:text-xl font-bold ${s.pnl_month >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {formatPnl(s.pnl_month)}
                <span className="text-xs font-normal text-white/40 ml-1">USDT</span>
              </div>
            </div>

            {/* Period PnL row */}
            <div className="grid grid-cols-4 gap-1.5 sm:gap-2 mb-3">
              {[
                { label: "24ч", pnl: s.pnl_24h, trades: s.trades_24h },
                { label: "Сегодня", pnl: s.pnl_today, trades: s.trades_today },
                { label: "7 дн", pnl: s.pnl_week, trades: s.trades_week },
                { label: "30 дн", pnl: s.pnl_month, trades: s.trades_month },
              ].map((r) => (
                <div key={r.label} className="rounded-lg bg-white/5 p-2 text-center">
                  <div className="text-[9px] sm:text-[10px] text-white/40">{r.label}</div>
                  <div className={`text-[11px] sm:text-xs font-semibold ${r.pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {formatPnl(r.pnl)}
                  </div>
                  <div className="text-[8px] sm:text-[9px] text-white/30">{r.trades} сд.</div>
                </div>
              ))}
            </div>

            {/* Key metrics row */}
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5 sm:gap-2">
              <div className="rounded-lg bg-white/5 p-2 text-center">
                <div className="text-[9px] sm:text-[10px] text-white/40">Win Rate</div>
                <div className="text-xs sm:text-sm font-bold text-emerald-400">{s.win_rate}%</div>
              </div>
              <div className="rounded-lg bg-white/5 p-2 text-center">
                <div className="text-[9px] sm:text-[10px] text-white/40">PF</div>
                <div className={`text-xs sm:text-sm font-bold ${s.profit_factor >= 1 ? "text-emerald-400" : "text-red-400"}`}>
                  {s.profit_factor >= 999 ? "\u221e" : s.profit_factor.toFixed(2)}
                </div>
              </div>
              <div className="rounded-lg bg-white/5 p-2 text-center">
                <div className="text-[9px] sm:text-[10px] text-white/40">Кругов</div>
                <div className="text-xs sm:text-sm font-bold text-indigo-400">{s.total_rounds}</div>
              </div>
              <div className="rounded-lg bg-amber-400/10 p-2 text-center">
                <div className="text-[9px] sm:text-[10px] text-amber-300/70">Комиссия</div>
                <div className="text-[10px] sm:text-xs font-semibold text-amber-400">{s.total_commission.toFixed(4)}</div>
              </div>
              <div className="rounded-lg bg-white/5 p-2 text-center">
                <div className="text-[9px] sm:text-[10px] text-white/40">Просадка</div>
                <div className="text-[10px] sm:text-xs font-semibold text-red-400">{formatPnl(s.max_drawdown)}</div>
              </div>
              <div className="rounded-lg bg-white/5 p-2 text-center">
                <div className="text-[9px] sm:text-[10px] text-white/40">Объём</div>
                <div className="text-[10px] sm:text-xs font-semibold">${s.total_volume.toFixed(0)}</div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Demo data ───
const DEMO_DATA: DashboardData = {
  total_grids: 3,
  active_grids: 2,
  total_pnl: 142.58,
  total_trades: 47,
  win_rate: 72.3,
  strategies: [
    { strategy: "simple", grids_count: 1, active_count: 1, total_pnl: 42.18, total_trades: 15 },
    { strategy: "adaptive", grids_count: 1, active_count: 1, total_pnl: 108.8, total_trades: 28 },
    { strategy: "reverse", grids_count: 1, active_count: 0, total_pnl: -8.4, total_trades: 4 },
  ],
  positions: [
    { grid_id: "demo-1", grid_name: "BTC Grid", symbol: "BTC/USDT", strategy: "simple", status: "running", mode: "paper", side: "long", entry_price: 67500, current_levels: 6, filled_orders: 2, realized_pnl: 42.18, total_trades: 15, auto_convert_to: null, unconverted_pnl: 0 },
    { grid_id: "demo-2", grid_name: "ETH Adaptive", symbol: "ETH/USDT", strategy: "adaptive", status: "running", mode: "paper", side: "long", entry_price: 3250, current_levels: 10, filled_orders: 4, realized_pnl: 108.8, total_trades: 28, auto_convert_to: "USDC", unconverted_pnl: 0.85 },
    { grid_id: "demo-3", grid_name: "ETH Reverse", symbol: "ETH/USDT", strategy: "reverse", status: "stopped", mode: "paper", side: "long", entry_price: 3100, current_levels: 6, filled_orders: 0, realized_pnl: -8.4, total_trades: 4, auto_convert_to: null, unconverted_pnl: 0 },
  ],
  equity_curve: [
    { date: "2026-05-01", value: 0, label: "1 мая" },
    { date: "2026-05-03", value: 12.5, label: "3 мая" },
    { date: "2026-05-05", value: 38.2, label: "5 мая" },
    { date: "2026-05-07", value: 55.0, label: "7 мая" },
    { date: "2026-05-09", value: 89.4, label: "9 мая" },
    { date: "2026-05-11", value: 120.1, label: "11 мая" },
    { date: "2026-05-13", value: 142.58, label: "13 мая" },
  ],
};

// ─── BotControlPanel ───
function BotControlPanel() {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  const { data: status } = useQuery({
    queryKey: ["bot-status"],
    queryFn: fetchBotStatus,
    refetchInterval: 10_000,
  });

  const canManage = user?.role === "admin" || user?.role === "superadmin" || user?.role === "ultraadmin";
  const isSuperadmin = user?.role === "superadmin" || user?.role === "ultraadmin";

  const handleEmergencyStop = async () => {
    if (!confirm("\u26a0\ufe0f \u0410\u0412\u0410\u0420\u0418\u0419\u041d\u0410\u042f \u041e\u0421\u0422\u0410\u041d\u041e\u0412\u041a\u0410\n\n\u0412\u0441\u0435 \u0441\u0435\u0442\u043a\u0438 \u0431\u0443\u0434\u0443\u0442 \u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u044b, \u0412\u0421\u0415 \u043e\u0440\u0434\u0435\u0440\u0430 \u043d\u0430 \u0431\u0438\u0440\u0436\u0435 \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u044b.\n\n\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c?")) return;
    setLoading("emergency"); setError("");
    try {
      const result = await botEmergencyStop();
      alert(`\u041e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u043e \u0441\u0435\u0442\u043e\u043a: ${result.stopped_grids}\n\u041e\u0442\u043c\u0435\u043d\u0435\u043d\u043e \u043e\u0440\u0434\u0435\u0440\u043e\u0432: ${result.cancelled_orders}${result.errors.length ? `\n\u041e\u0448\u0438\u0431\u043a\u0438: ${result.errors.join(", ")}` : ""}`);
      void queryClient.invalidateQueries({ queryKey: ["bot-status"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["grids"] });
    } catch { setError("\u041e\u0448\u0438\u0431\u043a\u0430 \u0430\u0432\u0430\u0440\u0438\u0439\u043d\u043e\u0439 \u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438"); } finally { setLoading(""); }
  };

  const handleStopAll = async () => {
    if (!confirm("\u041e\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c \u0432\u0441\u0435 \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0435 \u0441\u0435\u0442\u043a\u0438?")) return;
    setLoading("stop"); setError("");
    try {
      await botStopAll();
      void queryClient.invalidateQueries({ queryKey: ["bot-status"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    } catch { setError("\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0435"); } finally { setLoading(""); }
  };

  const handleRestart = async () => {
    if (!confirm("\u041f\u0435\u0440\u0435\u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0432\u043e\u0440\u043a\u0435\u0440? \u0412\u0441\u0435 \u0441\u0435\u0442\u043a\u0438 \u0431\u0443\u0434\u0443\u0442 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u044b.")) return;
    setLoading("restart"); setError("");
    try {
      await botRestart();
      void queryClient.invalidateQueries({ queryKey: ["bot-status"] });
    } catch { setError("\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u043f\u0435\u0440\u0435\u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0435"); } finally { setLoading(""); }
  };

  if (!status) return null;

  return (
    <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div className={`h-3 w-3 rounded-full ${status.online ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]" : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]"}`} />
        <div>
          <div className="text-sm font-medium">Бот {status.online ? "работает" : "оффлайн"}</div>
          <div className="text-xs text-hint">{status.online ? `${status.active_grids} активных сеток` : "Воркер не отвечает"}</div>
        </div>
      </div>
      {canManage && (
        <div className="flex flex-wrap items-center gap-2">
          {error && <span className="text-xs text-red-300">{error}</span>}
          <Button onClick={handleEmergencyStop} disabled={loading !== "" || !status.online || status.active_grids === 0}
            className="flex items-center gap-1 text-[11px] sm:text-sm sm:gap-1.5 border-red-500/40 bg-red-600/20 text-red-100 shadow-[0_0_12px_rgba(239,68,68,0.2)] hover:bg-red-600/30">
            <OctagonX size={12} /> {loading === "emergency" ? "Стоп..." : "Авария"}
          </Button>
          <Button onClick={handleStopAll} disabled={loading !== "" || !status.online || status.active_grids === 0}
            className="flex items-center gap-1 text-[11px] sm:text-sm sm:gap-1.5 border-red-400/20 bg-red-400/10 text-red-100 hover:bg-red-400/20">
            <Square size={12} /> {loading === "stop" ? "Стоп..." : "Стоп все"}
          </Button>
          {isSuperadmin && (
            <Button onClick={handleRestart} disabled={loading !== ""}
              className="flex items-center gap-1 text-[11px] sm:text-sm sm:gap-1.5 border-amber-400/20 bg-amber-400/10 text-amber-100 hover:bg-amber-400/20">
              <RefreshCw size={12} className={loading === "restart" ? "animate-spin" : ""} />
              {loading === "restart" ? "..." : "Рестарт"}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Per-Grid Analytics Section ───
function GridAnalyticsSection({ grid }: { grid: GridAnalytics }) {
  const stats = grid.period_stats;
  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="grid grid-cols-2 gap-2 sm:gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard label="Чистая прибыль" value={`${formatPnl(stats.pnl_month)} USDT`} icon={DollarSign} trend={stats.pnl_month >= 0 ? "up" : "down"} subtitle="за 30 дней (за вычетом комиссии)" />
        <MetricCard label="За 24 часа" value={`${formatPnl(stats.pnl_24h)} USDT`} icon={Clock} trend={stats.pnl_24h >= 0 ? "up" : "down"} subtitle={`${stats.trades_24h} сделок`} />
        <MetricCard label="Win Rate" value={`${stats.win_rate}%`} icon={Percent} />
        <MetricCard label="Кругов" value={String(stats.total_rounds)} icon={RefreshCw} subtitle="завершённых циклов" />
        <MetricCard label="Комиссия" value={`${stats.total_commission.toFixed(4)} USDT`} icon={DollarSign} subtitle="оценка за период" />
        <MetricCard label="Просадка" value={`${formatPnl(stats.max_drawdown)} USDT`} icon={TrendingDown} />
      </div>

      {/* PnL chart + Activity */}
      <div className="grid gap-3 sm:gap-4 lg:grid-cols-2">
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <h3 className="mb-2 text-sm font-semibold">Динамика чистой прибыли</h3>
          <GridPnlChart points={grid.pnl_series} />
        </div>
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <h3 className="mb-2 text-sm font-semibold">Активность торговли</h3>
          <TradeActivityChart data={grid.daily_activity} />
        </div>
      </div>

      {/* Hourly + Drawdown */}
      <div className="grid gap-3 sm:gap-4 lg:grid-cols-2">
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <h3 className="mb-2 text-sm font-semibold">Активность по часам</h3>
          <HourlyChart data={grid.hourly_distribution} />
        </div>
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <h3 className="mb-2 text-sm font-semibold">Просадка (Drawdown)</h3>
          <DrawdownChart data={grid.drawdown_curve} />
        </div>
      </div>

      {/* Recent trades */}
      <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
        <h3 className="mb-2 text-sm font-semibold">Последние сделки ({grid.grid_name})</h3>
        <RecentTradesFeed trades={grid.recent_trades} />
      </div>
    </div>
  );
}

// ─── Section Config ───
const SECTIONS = [
  { key: "metrics", label: "Основные метрики" },
  { key: "gridPnl", label: "Прибыль по сеткам" },
  { key: "balances", label: "Баланс кошельков" },
  { key: "equity", label: "Кривая доходности" },
  { key: "strategies", label: "Стратегии" },
  { key: "positions", label: "Позиции" },
  { key: "analytics", label: "Аналитика (селектор)" },
  { key: "pnlTimeline", label: "Динамика прибыли" },
  { key: "periodStats", label: "Прибыль и потери" },
  { key: "tradeActivity", label: "Активность торговли" },
  { key: "extendedMetrics", label: "Ключевые метрики" },
  { key: "drawdown", label: "Просадка" },
  { key: "hourly", label: "Активность по часам" },
  { key: "gridComparison", label: "Сравнение сеток" },
  { key: "recentTrades", label: "Последние сделки" },
] as const;

type SectionKey = (typeof SECTIONS)[number]["key"];
type SectionVisibility = Record<SectionKey, boolean>;

const DEFAULT_ORDER: SectionKey[] = SECTIONS.map((s) => s.key);
const STORAGE_VIS = "dashboard_sections";
const STORAGE_ORDER = "dashboard_order";

function loadVisibility(): SectionVisibility {
  try {
    const raw = localStorage.getItem(STORAGE_VIS);
    if (raw) return { ...Object.fromEntries(SECTIONS.map((s) => [s.key, true])), ...JSON.parse(raw) };
  } catch {}
  return Object.fromEntries(SECTIONS.map((s) => [s.key, true])) as SectionVisibility;
}

function saveVisibility(v: SectionVisibility) {
  localStorage.setItem(STORAGE_VIS, JSON.stringify(v));
}

function loadOrder(): SectionKey[] {
  try {
    const raw = localStorage.getItem(STORAGE_ORDER);
    if (raw) {
      const parsed = JSON.parse(raw) as SectionKey[];
      // ensure all keys present
      const missing = DEFAULT_ORDER.filter((k) => !parsed.includes(k));
      return [...parsed, ...missing];
    }
  } catch {}
  return [...DEFAULT_ORDER];
}

function saveOrder(order: SectionKey[]) {
  localStorage.setItem(STORAGE_ORDER, JSON.stringify(order));
}

const SECTION_LABELS: Record<SectionKey, string> = Object.fromEntries(SECTIONS.map((s) => [s.key, s.label])) as any;

// ─── Sortable item for settings panel ───
function SortableSettingsItem({ id, label, enabled, onToggle }: { id: string; label: string; enabled: boolean; onToggle: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, zIndex: isDragging ? 50 : undefined, opacity: isDragging ? 0.8 : 1 };

  return (
    <div ref={setNodeRef} style={style} className={`flex items-center gap-2 rounded-xl px-2 py-2.5 text-sm transition ${isDragging ? "bg-white/10 shadow-lg" : "hover:bg-white/5"}`}>
      <button {...attributes} {...listeners} className="cursor-grab touch-none rounded p-1 text-white/30 hover:text-white/60 active:cursor-grabbing">
        <GripVertical size={16} />
      </button>
      <span className={`flex-1 ${enabled ? "text-white" : "text-white/40"}`}>{label}</span>
      <button onClick={onToggle} className="shrink-0">
        <div className={`h-6 w-11 rounded-full transition-colors relative ${enabled ? "bg-indigo-500" : "bg-white/15"}`}>
          <div className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${enabled ? "translate-x-[22px]" : "translate-x-0.5"}`} />
        </div>
      </button>
    </div>
  );
}

// ─── Settings Panel with drag reorder ───
function SettingsPanel({
  visible,
  order,
  onChangeVis,
  onChangeOrder,
  onClose,
}: {
  visible: SectionVisibility;
  order: SectionKey[];
  onChangeVis: (v: SectionVisibility) => void;
  onChangeOrder: (o: SectionKey[]) => void;
  onClose: () => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 5 } }),
  );

  const toggle = (key: SectionKey) => {
    const next = { ...visible, [key]: !visible[key] };
    saveVisibility(next);
    onChangeVis(next);
  };

  const allOn = order.every((k) => visible[k]);
  const toggleAll = () => {
    const next = Object.fromEntries(order.map((k) => [k, !allOn])) as SectionVisibility;
    saveVisibility(next);
    onChangeVis(next);
  };

  const resetAll = () => {
    const defVis = Object.fromEntries(SECTIONS.map((s) => [s.key, true])) as SectionVisibility;
    saveVisibility(defVis);
    saveOrder([...DEFAULT_ORDER]);
    onChangeVis(defVis);
    onChangeOrder([...DEFAULT_ORDER]);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIdx = order.indexOf(active.id as SectionKey);
      const newIdx = order.indexOf(over.id as SectionKey);
      const newOrder = arrayMove(order, oldIdx, newIdx);
      saveOrder(newOrder);
      onChangeOrder(newOrder);
    }
  };

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      initial={{ backgroundColor: "rgba(0,0,0,0)" }}
      animate={{ backgroundColor: "rgba(0,0,0,0.6)" }}
      exit={{ backgroundColor: "rgba(0,0,0,0)" }}
      transition={{ duration: 0.2 }}
      style={{ backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <motion.div
        className="w-full max-w-md max-h-[85dvh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-white/10 bg-[#0d1324] p-4 sm:p-6 shadow-2xl"
        initial={{ opacity: 0, y: 60, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 40, scale: 0.97 }}
        transition={{ type: "spring", damping: 28, stiffness: 350 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Настройки дашборда</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-white/50 hover:bg-white/10 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="mb-3 flex gap-2">
          <button
            onClick={toggleAll}
            className="flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm font-medium text-white/70 hover:bg-white/10 transition"
          >
            {allOn ? "Скрыть все" : "Показать все"}
          </button>
          <button
            onClick={resetAll}
            className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm font-medium text-white/70 hover:bg-white/10 transition"
          >
            <RotateCcw size={14} />
            Сброс
          </button>
        </div>

        <p className="mb-2 text-[11px] text-white/30">Перетащите секции для изменения порядка</p>

        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={order} strategy={verticalListSortingStrategy}>
            <div className="space-y-0.5">
              {order.map((key) => (
                <SortableSettingsItem key={key} id={key} label={SECTION_LABELS[key]} enabled={visible[key]} onToggle={() => toggle(key)} />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      </motion.div>
    </motion.div>
  );
}

// ─── Sortable Dashboard Section Wrapper ───
function SortableSection({ id, children }: { id: string; children: ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });

  return (
    <motion.div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 40 : undefined,
        opacity: isDragging ? 0.85 : 1,
      }}
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10, scale: 0.98 }}
      transition={{ type: "spring", damping: 25, stiffness: 300 }}
      className={`group relative ${isDragging ? "ring-2 ring-indigo-500/40 rounded-2xl" : ""}`}
    >
      <button
        {...attributes}
        {...listeners}
        className="absolute -left-1 top-3 z-10 cursor-grab touch-none rounded-lg bg-white/5 p-1 text-white/0 opacity-0 transition group-hover:text-white/40 group-hover:opacity-100 hover:!text-white/70 active:cursor-grabbing sm:-left-2 sm:top-4"
        title="Перетащить"
      >
        <GripVertical size={16} />
      </button>
      {children}
    </motion.div>
  );
}

// ─── Main Dashboard ───
export function DashboardPage() {
  const isGuest = useAuthStore((state) => state.isGuest);
  const [selectedGrid, setSelectedGrid] = useState<string | null>(null);
  const [sectionVis, setSectionVis] = useState<SectionVisibility>(loadVisibility);
  const [sectionOrder, setSectionOrder] = useState<SectionKey[]>(loadOrder);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const show = (key: SectionKey) => sectionVis[key];

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
  );

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
    enabled: !isGuest,
    refetchInterval: 10_000,
  });

  const { data: balances } = useQuery({
    queryKey: ["balances"],
    queryFn: fetchBalances,
    enabled: !isGuest,
    refetchInterval: 30_000,
  });

  const { data: analytics } = useQuery({
    queryKey: ["analytics"],
    queryFn: () => fetchAnalytics(30),
    enabled: !isGuest,
    refetchInterval: 10_000,
  });

  const dashboard = isGuest ? DEMO_DATA : data;

  const selectedGridAnalytics = useMemo(() => {
    if (!analytics || !selectedGrid) return null;
    return analytics.grids.find((g) => g.grid_id === selectedGrid) || null;
  }, [analytics, selectedGrid]);

  const activeStats = selectedGridAnalytics?.period_stats || analytics?.total_stats || analytics?.period_stats;
  const activeDailyActivity = selectedGridAnalytics?.daily_activity || analytics?.total_daily_activity || analytics?.daily_activity;
  const activeHourly = selectedGridAnalytics?.hourly_distribution || analytics?.hourly_distribution;
  const activeDrawdown = selectedGridAnalytics?.drawdown_curve || analytics?.drawdown_curve;
  const activeRecentTrades = selectedGridAnalytics?.recent_trades || analytics?.recent_trades;

  // Section renderers
  const sectionRenderers: Record<SectionKey, () => ReactNode> = {
    metrics: () => (
      <div className="grid grid-cols-2 gap-2 sm:gap-4 lg:grid-cols-4">
        <MetricCard label="Всего сеток" value={String(dashboard!.total_grids)} icon={BarChart3} />
        <MetricCard label="Активных" value={String(dashboard!.active_grids)} icon={Activity} />
        <MetricCard
          label="Чистая прибыль"
          value={`${formatPnl(dashboard!.total_pnl)} USDT`}
          icon={DollarSign}
          trend={dashboard!.total_pnl > 0 ? "up" : dashboard!.total_pnl < 0 ? "down" : "neutral"}
          subtitle={analytics?.total_stats ? `Комиссия: ~${analytics.total_stats.total_commission.toFixed(4)} USDT` : undefined}
        />
        <MetricCard
          label="Win Rate"
          value={`${dashboard!.win_rate}%`}
          icon={Percent}
          subtitle={analytics?.total_stats ? `${analytics.total_stats.total_rounds} кругов` : undefined}
        />
      </div>
    ),
    gridPnl: () =>
      !isGuest && analytics && analytics.grids.length > 0 ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 size={18} className="text-indigo-400" />
            <h2 className="text-base sm:text-lg font-semibold">Прибыль и метрики по сеткам</h2>
          </div>
          <GridPnlCards grids={analytics.grids} />
        </div>
      ) : null,
    balances: () =>
      !isGuest && balances && balances.length > 0 ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <DollarSign size={18} className="text-emerald-400" />
            <h2 className="text-sm sm:text-lg font-semibold">Баланс кошельков</h2>
          </div>
          <BalancesPanel balances={balances} />
        </div>
      ) : null,
    equity: () => (
      <div className="grid gap-3 sm:gap-4 lg:grid-cols-3">
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm sm:text-lg font-semibold">Кривая доходности</h2>
            <span className="text-xs text-white/40">{dashboard!.total_trades} трейдов</span>
          </div>
          <EquityChart data={dashboard!.equity_curve} />
        </div>
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <h2 className="mb-3 text-sm sm:text-lg font-semibold">Распределение</h2>
          <AllocationChart strategies={dashboard!.strategies} />
        </div>
      </div>
    ),
    strategies: () => (
      <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
        <div className="mb-3 flex items-center gap-2">
          <Zap size={18} className="text-indigo-400" />
          <h2 className="text-sm sm:text-lg font-semibold">Стратегии</h2>
        </div>
        <StrategiesPanel strategies={dashboard!.strategies} />
      </div>
    ),
    positions: () => (
      <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
        <h2 className="mb-3 text-sm sm:text-lg font-semibold">Позиции</h2>
        <PositionsTable positions={dashboard!.positions} />
      </div>
    ),
    analytics: () =>
      !isGuest && analytics ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm sm:text-lg font-semibold">Аналитика</h2>
            <div className="flex items-center gap-2 text-[10px] text-white/30">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              обновляется каждые 10 сек
            </div>
          </div>
          <GridSelector
            grids={analytics.grids.map((g) => ({ grid_id: g.grid_id, grid_name: g.grid_name, symbol: g.symbol }))}
            selected={selectedGrid}
            onSelect={setSelectedGrid}
          />
        </div>
      ) : null,
    pnlTimeline: () =>
      !isGuest && analytics && !selectedGridAnalytics ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp size={18} className="text-indigo-400" />
            <h2 className="text-sm sm:text-lg font-semibold">Динамика чистой прибыли по сеткам</h2>
          </div>
          <PnlTimelineChart series={analytics.pnl_series} />
        </div>
      ) : null,
    periodStats: () =>
      !isGuest && analytics && !selectedGridAnalytics && activeStats ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <DollarSign size={18} className="text-emerald-400" />
            <h2 className="text-sm sm:text-lg font-semibold">Прибыль и потери (чистые)</h2>
          </div>
          <PeriodStatsPanel stats={activeStats} />
        </div>
      ) : null,
    tradeActivity: () =>
      !isGuest && analytics && !selectedGridAnalytics && activeDailyActivity ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 size={18} className="text-indigo-400" />
            <h2 className="text-sm sm:text-lg font-semibold">Активность торговли</h2>
          </div>
          <TradeActivityChart data={activeDailyActivity} />
        </div>
      ) : null,
    extendedMetrics: () =>
      !isGuest && analytics && !selectedGridAnalytics && activeStats ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <Zap size={18} className="text-amber-400" />
            <h2 className="text-sm sm:text-lg font-semibold">Ключевые метрики</h2>
          </div>
          <ExtendedMetrics stats={activeStats} />
        </div>
      ) : null,
    drawdown: () =>
      !isGuest && analytics && !selectedGridAnalytics && activeDrawdown ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingDown size={18} className="text-red-400" />
            <h2 className="text-sm sm:text-lg font-semibold">Просадка (Drawdown)</h2>
          </div>
          <DrawdownChart data={activeDrawdown} />
        </div>
      ) : null,
    hourly: () =>
      !isGuest && analytics && !selectedGridAnalytics && activeHourly ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 size={18} className="text-cyan-400" />
            <h2 className="text-sm sm:text-lg font-semibold">Активность по часам</h2>
          </div>
          <HourlyChart data={activeHourly} />
        </div>
      ) : null,
    gridComparison: () =>
      !isGuest && analytics && !selectedGridAnalytics ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 size={18} className="text-indigo-400" />
            <h2 className="text-sm sm:text-lg font-semibold">Сравнение сеток</h2>
          </div>
          <GridComparisonTable grids={analytics.grid_comparison} />
        </div>
      ) : null,
    recentTrades: () =>
      !isGuest && analytics && !selectedGridAnalytics && activeRecentTrades ? (
        <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
          <div className="mb-3 flex items-center gap-2">
            <Activity size={18} className="text-cyan-400" />
            <h2 className="text-sm sm:text-lg font-semibold">Последние сделки</h2>
          </div>
          <RecentTradesFeed trades={activeRecentTrades} />
        </div>
      ) : null,
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIdx = sectionOrder.indexOf(active.id as SectionKey);
      const newIdx = sectionOrder.indexOf(over.id as SectionKey);
      const newOrder = arrayMove(sectionOrder, oldIdx, newIdx);
      saveOrder(newOrder);
      setSectionOrder(newOrder);
    }
  };

  if (!isGuest && isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
      </div>
    );
  }

  if (!dashboard) return <div className="text-center text-white/50">Не удалось загрузить данные</div>;

  // Visible section keys in order
  const visibleKeys = sectionOrder.filter((k) => show(k));

  return (
    <div className="w-full max-w-full space-y-3 sm:space-y-5 overflow-hidden">
      {isGuest && (
        <div className="rounded-xl border border-indigo-400/20 bg-indigo-400/10 p-3 sm:p-4">
          <div className="text-sm text-white/75">Вы в демо-режиме. Данные ниже — примерные. Войдите для реальной статистики.</div>
        </div>
      )}

      {!isGuest && <BotControlPanel />}

      {/* Settings button */}
      <div className="flex justify-end">
        <button
          onClick={() => setSettingsOpen(true)}
          className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/60 hover:bg-white/10 hover:text-white transition"
        >
          <Settings size={14} />
          Настройки
        </button>
      </div>

      <AnimatePresence>
        {settingsOpen && (
          <SettingsPanel
            visible={sectionVis}
            order={sectionOrder}
            onChangeVis={setSectionVis}
            onChangeOrder={setSectionOrder}
            onClose={() => setSettingsOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Per-grid detailed view (not sortable, shown when grid selected) */}
      {selectedGridAnalytics && !isGuest && analytics && show("analytics") && (
        <>
          <div className="rounded-xl sm:rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 sm:p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm sm:text-lg font-semibold">Аналитика</h2>
              <div className="flex items-center gap-2 text-[10px] text-white/30">
                <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                обновляется каждые 10 сек
              </div>
            </div>
            <GridSelector
              grids={analytics.grids.map((g) => ({ grid_id: g.grid_id, grid_name: g.grid_name, symbol: g.symbol }))}
              selected={selectedGrid}
              onSelect={setSelectedGrid}
            />
          </div>
          <GridAnalyticsSection grid={selectedGridAnalytics} />
        </>
      )}

      {/* Sortable sections */}
      {!selectedGridAnalytics && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={visibleKeys} strategy={verticalListSortingStrategy}>
            <AnimatePresence mode="popLayout">
              {visibleKeys.map((key) => {
                const content = sectionRenderers[key]();
                if (!content) return null;
                return (
                  <SortableSection key={key} id={key}>
                    {content}
                  </SortableSection>
                );
              })}
            </AnimatePresence>
          </SortableContext>
        </DndContext>
      )}
    </div>
  );
}
