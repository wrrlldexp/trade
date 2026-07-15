import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  DollarSign,
  OctagonX,
  RefreshCw,
  Square,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useState } from "react";
import {
  Area,
  AreaChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { botEmergencyStop, botRestart, botStopAll, fetchBotStatus } from "../api/bot";
import { fetchAnalytics, fetchBalances, fetchDashboard } from "../api/dashboard";
import type { AccountBalance, PeriodStats } from "../api/dashboard";
import { fetchGridCharts, listGrids } from "../api/grids";
import { useAuthStore } from "../store/auth";
import { Button } from "../components/Button";

// ─── Helpers ───

function formatPnl(value: number) {
  const sign = value >= 0 ? "+" : "";
  const abs = Math.abs(value);
  const decimals = abs > 0 && abs < 0.01 ? 8 : abs < 1 ? 4 : 2;
  const formatted = value.toFixed(decimals).replace(/0+$/, "").replace(/\.$/, "");
  return `${sign}${formatted}`;
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

const tooltipStyle = {
  background: "rgba(15,23,42,0.95)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 12,
  color: "#fff",
  fontSize: 12,
};

const PERIODS = [
  { label: "1ч", hours: 1 },
  { label: "6ч", hours: 6 },
  { label: "24ч", hours: 24 },
  { label: "3д", hours: 72 },
  { label: "7д", hours: 168 },
  { label: "30д", hours: 720 },
];

// ─── MetricCard ───

function MetricCard({
  label,
  value,
  trend,
  subtitle,
}: {
  label: string;
  value: string;
  trend?: "up" | "down" | "neutral";
  subtitle?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
      <div className="text-xs text-white/50">{label}</div>
      <div className="mt-1 text-2xl font-bold tracking-tight">
        {value}
        {trend && trend !== "neutral" && (
          <span className={`ml-2 inline-flex text-sm ${trend === "up" ? "text-emerald-400" : "text-red-400"}`}>
            {trend === "up" ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
          </span>
        )}
      </div>
      {subtitle && <div className="mt-1 text-[11px] text-white/40">{subtitle}</div>}
    </div>
  );
}

// ─── BalancesPanel ───

function BalancesPanel({ balances }: { balances: AccountBalance[] }) {
  if (!balances || balances.length === 0) return null;

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
      <h2 className="mb-3 text-lg font-semibold flex items-center gap-2">
        <Wallet size={18} className="text-amber-400" />
        Балансы
      </h2>
      <div className="space-y-3">
        {balances.map((acc) => (
          <div key={acc.account_id} className="rounded-xl bg-white/5 p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">{acc.name}</span>
              <span className="text-[10px] text-white/40 uppercase">
                {acc.exchange}{acc.testnet ? " testnet" : ""}
              </span>
            </div>
            {acc.error ? (
              <div className="text-xs text-red-400">{acc.error}</div>
            ) : (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
                {acc.currencies
                  .filter((c) => parseFloat(c.total) > 0)
                  .map((c) => (
                    <div key={c.currency} className="text-xs">
                      <span className="text-white/60">{c.currency}: </span>
                      <span className="font-mono text-white/90">
                        {parseFloat(c.total) > 1000
                          ? parseFloat(c.total).toFixed(2)
                          : parseFloat(c.total) > 1
                            ? parseFloat(c.total).toFixed(4)
                            : c.total}
                      </span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── GridCharts (4 panels) with grid switcher ───

import type { Grid } from "../api/types";

function GridChartsPanel({ grids }: { grids: Grid[] }) {
  const [selectedId, setSelectedId] = useState(
    () => grids.find((g) => g.status === "running")?.id || grids[0]?.id || "",
  );
  const [hours, setHours] = useState(24);

  const { data: chartData } = useQuery({
    queryKey: ["grid-charts-dashboard", selectedId, hours],
    queryFn: () => fetchGridCharts(selectedId, hours),
    enabled: !!selectedId,
    refetchInterval: 30_000,
  });

  if (!selectedId || !chartData) {
    return null;
  }

  const d = chartData;
  const useDate = hours > 24;
  const fmt = useDate ? formatDate : formatTime;

  const pnlData = d.pnl.map((p) => ({ t: fmt(p.t), pnl: p.pnl }));
  const lastPnl = d.pnl.length > 0 ? d.pnl[d.pnl.length - 1].pnl : 0;

  const priceData = d.price.map((p) => ({ t: fmt(p.t), mid: p.mid }));
  const lastPrice = d.price.length > 0 ? d.price[d.price.length - 1].mid : 0;

  const equityData = d.equity.map((p) => ({ t: fmt(p.t), equity: p.equity }));
  const lastEquity = d.equity.length > 0 ? d.equity[d.equity.length - 1].equity : 0;

  const ddData = d.drawdown.map((p) => ({ t: fmt(p.t), dd: p.drawdown_pct }));
  const lastDd = d.drawdown.length > 0 ? d.drawdown[d.drawdown.length - 1].drawdown_pct : 0;

  return (
    <div className="space-y-4">
      {/* Grid selector + Period */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Grid tabs */}
        <div className="flex gap-1 overflow-x-auto rounded-xl bg-white/5 p-1">
          {grids.map((g) => (
            <button
              key={g.id}
              onClick={() => setSelectedId(g.id)}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-xs transition-colors ${
                selectedId === g.id
                  ? "bg-indigo-500/30 text-indigo-300"
                  : "text-white/50 hover:text-white/80"
              }`}
            >
              {g.name}
              {g.status === "running" && (
                <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
              )}
            </button>
          ))}
        </div>

        {/* Period selector */}
        <div className="flex gap-1 rounded-xl bg-white/5 p-1">
          {PERIODS.map((p) => (
            <button
              key={p.hours}
              onClick={() => setHours(p.hours)}
              className={`rounded-lg px-2.5 py-1 text-xs transition-colors ${
                hours === p.hours
                  ? "bg-indigo-500/30 text-indigo-300"
                  : "text-white/50 hover:text-white/80"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Grid info */}
      <div>
        <span className="text-xs text-white/40">{d.symbol} · {d.points} точек</span>
      </div>

      {/* 4 Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Прибыль */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <DollarSign size={14} className="text-emerald-400" />
              Прибыль
            </h3>
            <span className={`text-sm font-mono ${lastPnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {formatPnl(lastPnl)} USDT
            </span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={pnlData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="dashPnlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={lastPnl >= 0 ? "#34d399" : "#f87171"} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={lastPnl >= 0 ? "#34d399" : "#f87171"} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 9 }} axisLine={false} tickLine={false} width={50} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${formatPnl(v)} USDT`, "PnL"]} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" strokeDasharray="3 3" />
              <Area type="monotone" dataKey="pnl" stroke={lastPnl >= 0 ? "#34d399" : "#f87171"} strokeWidth={2} fill="url(#dashPnlGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Курс */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <TrendingUp size={14} className="text-blue-400" />
              Курс
            </h3>
            <span className="text-sm font-mono text-blue-300">
              {lastPrice.toFixed(lastPrice > 100 ? 2 : 4)}
            </span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={priceData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <XAxis dataKey="t" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 9 }} axisLine={false} tickLine={false} width={60} domain={["auto", "auto"]} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v.toFixed(v > 100 ? 2 : 6), ""]} />
              <Line type="monotone" dataKey="mid" stroke="#60a5fa" strokeWidth={2} dot={false} name="Цена" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Остаток */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <Wallet size={14} className="text-amber-400" />
              Остаток
            </h3>
            <div className="text-right">
              <span className="text-sm font-mono text-amber-300">
                {lastEquity > 0 ? lastEquity.toFixed(2) : "—"} USDT
              </span>
              {d.start_amount > 0 && (
                <div className="text-[10px] text-white/40">старт: {d.start_amount.toFixed(2)}</div>
              )}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={equityData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="dashEqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#fbbf24" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 9 }} axisLine={false} tickLine={false} width={55} domain={["auto", "auto"]} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v.toFixed(2)} USDT`, "Остаток"]} />
              {d.start_amount > 0 && (
                <ReferenceLine y={d.start_amount} stroke="rgba(251,191,36,0.3)" strokeDasharray="5 5" />
              )}
              <Area type="monotone" dataKey="equity" stroke="#fbbf24" strokeWidth={2} fill="url(#dashEqGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Просадка */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <TrendingDown size={14} className="text-rose-400" />
              Просадка
            </h3>
            <span className={`text-sm font-mono ${lastDd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {lastDd >= 0 ? "+" : ""}{lastDd.toFixed(2)}%
            </span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={ddData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="dashDdGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f87171" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#f87171" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 9 }} axisLine={false} tickLine={false} width={45} unit="%" />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v.toFixed(2)}%`, "Просадка"]} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="3 3" />
              <Area type="monotone" dataKey="dd" stroke="#f87171" strokeWidth={2} fill="url(#dashDdGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

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
    if (!confirm("АВАРИЙНАЯ ОСТАНОВКА\n\nВсе сетки будут остановлены, ВСЕ ордера на бирже отменены.\n\nПродолжить?")) return;
    setLoading("emergency"); setError("");
    try {
      const result = await botEmergencyStop();
      alert(`Остановлено сеток: ${result.stopped_grids}\nОтменено ордеров: ${result.cancelled_orders}`);
      void queryClient.invalidateQueries({ queryKey: ["bot-status"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    } catch { setError("Ошибка"); } finally { setLoading(""); }
  };

  const handleStopAll = async () => {
    if (!confirm("Остановить все активные сетки?")) return;
    setLoading("stop"); setError("");
    try {
      await botStopAll();
      void queryClient.invalidateQueries({ queryKey: ["bot-status"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    } catch { setError("Ошибка"); } finally { setLoading(""); }
  };

  const handleRestart = async () => {
    if (!confirm("Перезагрузить воркер?")) return;
    setLoading("restart"); setError("");
    try {
      await botRestart();
      void queryClient.invalidateQueries({ queryKey: ["bot-status"] });
    } catch { setError("Ошибка"); } finally { setLoading(""); }
  };

  if (!status) return null;

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div className={`h-3 w-3 rounded-full ${status.online ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]" : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]"}`} />
        <div>
          <div className="text-sm font-medium">Бот {status.online ? "работает" : "оффлайн"}</div>
          <div className="text-xs text-white/50">{status.online ? `${status.active_grids} активных сеток` : "Воркер не отвечает"}</div>
        </div>
      </div>
      {canManage && (
        <div className="flex flex-wrap items-center gap-2">
          {error && <span className="text-xs text-red-300">{error}</span>}
          <Button onClick={handleEmergencyStop} disabled={loading !== "" || !status.online || status.active_grids === 0}
            className="flex items-center gap-1.5 text-sm border-red-500/40 bg-red-600/20 text-red-100 hover:bg-red-600/30">
            <OctagonX size={14} /> {loading === "emergency" ? "..." : "Авария"}
          </Button>
          <Button onClick={handleStopAll} disabled={loading !== "" || !status.online || status.active_grids === 0}
            className="flex items-center gap-1.5 text-sm border-red-400/20 bg-red-400/10 text-red-100 hover:bg-red-400/20">
            <Square size={14} /> {loading === "stop" ? "..." : "Стоп все"}
          </Button>
          {isSuperadmin && (
            <Button onClick={handleRestart} disabled={loading !== ""}
              className="flex items-center gap-1.5 text-sm border-amber-400/20 bg-amber-400/10 text-amber-100 hover:bg-amber-400/20">
              <RefreshCw size={14} className={loading === "restart" ? "animate-spin" : ""} />
              {loading === "restart" ? "..." : "Рестарт"}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Dashboard ───

export function DashboardPage() {
  const isGuest = useAuthStore((state) => state.isGuest);

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
    enabled: !isGuest,
    refetchInterval: 10_000,
  });

  const { data: analytics } = useQuery({
    queryKey: ["analytics"],
    queryFn: () => fetchAnalytics(30),
    enabled: !isGuest,
    refetchInterval: 60_000,
  });

  const { data: balances } = useQuery({
    queryKey: ["balances"],
    queryFn: fetchBalances,
    enabled: !isGuest,
    refetchInterval: 30_000,
  });

  const { data: grids } = useQuery({
    queryKey: ["grids"],
    queryFn: listGrids,
    enabled: !isGuest,
  });

  const stats: PeriodStats | undefined = analytics?.total_stats || analytics?.period_stats;

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
      </div>
    );
  }

  if (!dashboard) {
    return <div className="flex h-64 items-center justify-center text-white/40">Нет данных</div>;
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Bot control */}
      <BotControlPanel />

      {/* Key metrics: PnL, Drawdown, Trades */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Чистая прибыль"
          value={`${formatPnl(dashboard.total_pnl)} USDT`}
          trend={dashboard.total_pnl > 0 ? "up" : dashboard.total_pnl < 0 ? "down" : "neutral"}
          subtitle={stats ? `24ч: ${formatPnl(stats.pnl_24h)} | 7д: ${formatPnl(stats.pnl_week)}` : undefined}
        />
        <MetricCard
          label="Просадка"
          value={stats ? `${formatPnl(stats.max_drawdown)} USDT` : "0"}
          trend="down"
        />
        <MetricCard
          label="Сделок (циклов)"
          value={stats ? String(stats.total_rounds) : String(dashboard.total_trades)}
          subtitle={stats ? `24ч: ${stats.trades_24h} | 7д: ${stats.trades_week}` : undefined}
        />
        <MetricCard
          label="Активных сеток"
          value={String(dashboard.active_grids)}
          subtitle={`из ${dashboard.total_grids} всего`}
        />
      </div>

      {/* Balances */}
      {balances && balances.length > 0 && <BalancesPanel balances={balances} />}

      {/* 4 Charts with grid switcher */}
      {grids && grids.length > 0 && <GridChartsPanel grids={grids} />}

      {/* Per-grid summary */}
      {analytics && analytics.grids.length > 0 && (
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <h2 className="mb-3 text-lg font-semibold flex items-center gap-2">
            <Activity size={18} className="text-indigo-400" />
            Сетки
          </h2>
          <div className="space-y-2">
            {analytics.grids.map((g) => (
              <div key={g.grid_id} className="flex items-center justify-between rounded-xl bg-white/5 p-3">
                <div>
                  <div className="text-sm font-medium">{g.grid_name}</div>
                  <div className="text-xs text-white/40">{g.symbol} · {g.period_stats.total_rounds} сделок</div>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-semibold ${g.period_stats.pnl_month >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {formatPnl(g.period_stats.pnl_month)} USDT
                  </div>
                  <div className="text-[10px] text-white/40">просадка: {formatPnl(g.period_stats.max_drawdown)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default DashboardPage;
