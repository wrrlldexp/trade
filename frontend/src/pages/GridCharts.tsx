import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { useState } from "react";
import {
  Area,
  AreaChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";
import { ArrowLeft, TrendingUp, DollarSign, Wallet, TrendingDown } from "lucide-react";

import { fetchGridCharts } from "../api/grids";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";

const PERIODS = [
  { label: "1ч", hours: 1 },
  { label: "6ч", hours: 6 },
  { label: "24ч", hours: 24 },
  { label: "3д", hours: 72 },
  { label: "7д", hours: 168 },
  { label: "30д", hours: 720 },
];

const tooltipStyle = {
  background: "rgba(15,23,42,0.95)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 12,
  color: "#fff",
  fontSize: 12,
};

function formatTime(iso: string) {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function formatPnl(v: number) {
  const sign = v >= 0 ? "+" : "";
  const abs = Math.abs(v);
  const dec = abs > 0 && abs < 0.01 ? 8 : abs < 1 ? 4 : 2;
  return `${sign}${v.toFixed(dec).replace(/0+$/, "").replace(/\.$/, "")}`;
}

export function GridChartsPage() {
  const { gridId = "" } = useParams();
  const navigate = useNavigate();
  const [hours, setHours] = useState(24);

  const { data, isLoading, error } = useQuery({
    queryKey: ["grid-charts", gridId, hours],
    queryFn: () => fetchGridCharts(gridId, hours),
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3 text-white/40">
        <p>{error ? "Ошибка загрузки данных" : "Нет данных"}</p>
        <Button onClick={() => navigate(-1)} className="text-sm">Назад</Button>
      </div>
    );
  }

  const useDate = hours > 24;
  const fmt = useDate ? formatDate : formatTime;

  // PnL chart data
  const pnlData = data.pnl.map((p) => ({ t: fmt(p.t), pnl: p.pnl }));
  const lastPnl = data.pnl.length > 0 ? data.pnl[data.pnl.length - 1].pnl : 0;

  // Price chart data
  const priceData = data.price.map((p) => ({ t: fmt(p.t), mid: p.mid, bid: p.bid, ask: p.ask }));
  const lastPrice = data.price.length > 0 ? data.price[data.price.length - 1].mid : 0;

  // Equity chart data
  const equityData = data.equity.map((p) => ({ t: fmt(p.t), equity: p.equity }));
  const lastEquity = data.equity.length > 0 ? data.equity[data.equity.length - 1].equity : 0;

  // Drawdown chart data
  const ddData = data.drawdown.map((p) => ({ t: fmt(p.t), dd: p.drawdown_pct }));
  const lastDd = data.drawdown.length > 0 ? data.drawdown[data.drawdown.length - 1].drawdown_pct : 0;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="text-white/50 hover:text-white">
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1 className="text-xl font-bold">{data.grid_name}</h1>
            <span className="text-sm text-white/50">{data.symbol} · {data.points} точек</span>
          </div>
        </div>

        {/* Period selector */}
        <div className="flex gap-1 rounded-xl bg-white/5 p-1">
          {PERIODS.map((p) => (
            <button
              key={p.hours}
              onClick={() => setHours(p.hours)}
              className={`rounded-lg px-3 py-1 text-sm transition-colors ${
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

      {/* 4 Charts Grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* 1. Прибыль (PnL) */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <DollarSign size={16} className="text-emerald-400" />
              Прибыль
            </h2>
            <span className={`text-sm font-mono ${lastPnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {formatPnl(lastPnl)} USDT
            </span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={pnlData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={lastPnl >= 0 ? "#34d399" : "#f87171"} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={lastPnl >= 0 ? "#34d399" : "#f87171"} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={55} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${formatPnl(v)} USDT`, "PnL"]} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" strokeDasharray="3 3" />
              <Area type="monotone" dataKey="pnl" stroke={lastPnl >= 0 ? "#34d399" : "#f87171"} strokeWidth={2} fill="url(#pnlGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* 2. Курс */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <TrendingUp size={16} className="text-blue-400" />
              Курс
            </h2>
            <span className="text-sm font-mono text-blue-300">
              {lastPrice.toFixed(lastPrice > 100 ? 2 : 4)}
            </span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={priceData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <XAxis dataKey="t" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={65} domain={["auto", "auto"]} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v.toFixed(v > 100 ? 2 : 6), ""]} />
              <Line type="monotone" dataKey="mid" stroke="#60a5fa" strokeWidth={2} dot={false} name="Цена" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* 3. Остаток */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <Wallet size={16} className="text-amber-400" />
              Остаток
            </h2>
            <div className="text-right">
              <span className="text-sm font-mono text-amber-300">
                {lastEquity.toFixed(2)} USDT
              </span>
              {data.start_amount > 0 && (
                <div className="text-[10px] text-white/40">
                  старт: {data.start_amount.toFixed(2)}
                </div>
              )}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={equityData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#fbbf24" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={60} domain={["auto", "auto"]} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v.toFixed(2)} USDT`, "Остаток"]} />
              {data.start_amount > 0 && (
                <ReferenceLine y={data.start_amount} stroke="rgba(251,191,36,0.3)" strokeDasharray="5 5" label={{ value: "старт", fill: "rgba(255,255,255,0.3)", fontSize: 10 }} />
              )}
              <Area type="monotone" dataKey="equity" stroke="#fbbf24" strokeWidth={2} fill="url(#eqGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* 4. Просадка */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <TrendingDown size={16} className="text-rose-400" />
              Просадка
            </h2>
            <span className={`text-sm font-mono ${lastDd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {lastDd >= 0 ? "+" : ""}{lastDd.toFixed(2)}%
            </span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={ddData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f87171" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#f87171" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={50} unit="%" />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v.toFixed(2)}%`, "Просадка"]} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="3 3" />
              <Area type="monotone" dataKey="dd" stroke="#f87171" strokeWidth={2} fill="url(#ddGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default GridChartsPage;
