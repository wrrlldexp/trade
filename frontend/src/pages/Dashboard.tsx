import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  DollarSign,
  OctagonX,
  RefreshCw,
  Square,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useState } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { botEmergencyStop, botRestart, botStopAll, fetchBotStatus } from "../api/bot";
import { fetchAnalytics, fetchDashboard } from "../api/dashboard";
import type { DrawdownPoint, PeriodStats } from "../api/dashboard";
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

const tooltipStyle = {
  background: "rgba(15,23,42,0.95)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 12,
  color: "#fff",
  fontSize: 12,
};

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

// ─── DrawdownChart ───

function DrawdownChart({ data }: { data: DrawdownPoint[] }) {
  if (data.length === 0) return <div className="flex h-48 items-center justify-center text-sm text-white/40">Нет данных</div>;
  const chartData = data.map((d, i) => ({ idx: i, drawdown: d.drawdown }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
        <XAxis dataKey="idx" tick={false} axisLine={false} />
        <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={50} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v.toFixed(4)} USDT`, "Просадка"]} />
        <Area type="monotone" dataKey="drawdown" stroke="#f87171" fill="rgba(248,113,113,0.15)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── PnL Chart ───

function PnlChart({ data }: { data: { date: string; cumulative: number }[] }) {
  if (data.length === 0) return <div className="flex h-48 items-center justify-center text-sm text-white/40">Нет данных</div>;
  const chartData = data.map((d) => ({ date: d.date.slice(5, 16), value: d.cumulative }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
        <defs>
          <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#34d399" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="date" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={50} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${formatPnl(v)} USDT`, "PnL"]} />
        <Area type="monotone" dataKey="value" stroke="#34d399" strokeWidth={2} fill="url(#pnlGrad)" />
      </AreaChart>
    </ResponsiveContainer>
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

  // Collect PnL points from all grids for the chart
  const pnlPoints = analytics?.grids.flatMap((g) => g.pnl_series) || [];

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

      {/* PnL Chart */}
      <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
        <h2 className="mb-3 text-lg font-semibold flex items-center gap-2">
          <DollarSign size={18} className="text-emerald-400" />
          Прибыль
        </h2>
        <PnlChart data={pnlPoints} />
      </div>

      {/* Drawdown Chart */}
      {analytics?.drawdown_curve && analytics.drawdown_curve.length > 0 && (
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <h2 className="mb-3 text-lg font-semibold flex items-center gap-2">
            <TrendingDown size={18} className="text-red-400" />
            Просадка
          </h2>
          <DrawdownChart data={analytics.drawdown_curve} />
        </div>
      )}

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
