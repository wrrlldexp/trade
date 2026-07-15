import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useState } from "react";

import { listAccounts } from "../api/accounts";
import { createGrid } from "../api/grids";
import type { StrategyType } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { Select } from "../components/Select";

const STRATEGY_LABELS: Record<string, string> = {
  simple: "Простая",
  capitalization: "Капитализация",
  reverse: "Реверс",
  adaptive: "Адаптивная",
};

export function GridCreatePage() {
  const navigate = useNavigate();
  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: listAccounts });
  const [form, setForm] = useState({
    account_id: "",
    name: "BTC Grid",
    symbol: "BTC/USDT",
    mode: "paper",
    strategy: "simple" as StrategyType,
    lot_size: "0.1",
    lot_quote: "",
    profit_step: "50",
    grid_step: "100",
    levels_above: "3",
    levels_below: "3",
    rebuild_timeout_sec: "3600",
    adaptive_timer_sec: "15",
    auto_convert_to: "",
  });

  const [error, setError] = useState<string | null>(null);
  const isAdaptive = form.strategy === "adaptive" || form.strategy === "adaptive_cap";

  const submit = async () => {
    setError(null);
    if (!form.account_id) {
      setError("Выберите аккаунт");
      return;
    }
    try {
      const grid = await createGrid({
        ...form,
        lot_size: form.lot_size || null,
        lot_quote: form.lot_quote && form.lot_quote !== "0" ? form.lot_quote : null,
        levels_above: Number(form.levels_above) || 0,
        levels_below: Number(form.levels_below) || 0,
        rebuild_timeout_sec: Number(form.rebuild_timeout_sec) || 3600,
        adaptive_timer_sec: Number(form.adaptive_timer_sec) || 15,
        auto_convert_to: form.auto_convert_to || null,
      });
      navigate(`/grids/${grid.id}`);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: unknown } } };
      const detail = axiosErr?.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d: { loc?: string[]; msg?: string }) => `${(d.loc || []).join(".")}: ${d.msg}`).join("; "));
      } else {
        setError("Ошибка при создании сетки");
      }
    }
  };

  return (
    <Card className="space-y-4">
      <h1 className="text-2xl font-bold">Создать сетку</h1>
      <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Название" />
      <Input value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value })} placeholder="Пара" />
      <Select value={form.account_id} onChange={(event) => setForm({ ...form, account_id: event.target.value })}>
        <option value="">Выбери аккаунт</option>
        {accounts.map((account) => (
          <option key={account.id} value={account.id}>
            {account.name}
          </option>
        ))}
      </Select>
      <Select value={form.mode} onChange={(event) => setForm({ ...form, mode: event.target.value })}>
        <option value="paper">Paper</option>
        <option value="live">Live</option>
      </Select>
      <Select value={form.strategy} onChange={(event) => setForm({ ...form, strategy: event.target.value as StrategyType })}>
        {(Object.entries(STRATEGY_LABELS) as [StrategyType, string][]).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </Select>
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <Input value={form.lot_size} onChange={(event) => setForm({ ...form, lot_size: event.target.value })} placeholder="Lot size (базовая валюта)" />
          <div className="mt-1 text-[10px] text-white/30">Объём ордера в базовой валюте (напр. 0.00003 BTC). Используется если «Лот в USDT» пуст</div>
        </div>
        <div>
          <Input value={form.lot_quote} onChange={(event) => setForm({ ...form, lot_quote: event.target.value })} placeholder="Лот в USDT (рекомендуется)" />
          <div className="mt-1 text-[10px] text-white/30">Объём ордера в котировочной валюте (напр. 2.5 USDT). Пересчёт по курсу при каждом ордере — защита от утечки депозита</div>
        </div>
        <div>
          <Input value={form.profit_step} onChange={(event) => setForm({ ...form, profit_step: event.target.value })} placeholder="Profit step" />
          <div className="mt-1 text-[10px] text-white/30">Разница между buy и sell ценой = ваша прибыль с каждой сделки</div>
        </div>
        <div>
          <Input value={form.grid_step} onChange={(event) => setForm({ ...form, grid_step: event.target.value })} placeholder="Grid step" />
          <div className="mt-1 text-[10px] text-white/30">Расстояние между уровнями ордеров. Меньше = больше сделок</div>
        </div>
        <div>
          <Input value={form.levels_above} onChange={(event) => setForm({ ...form, levels_above: event.target.value })} placeholder="Levels above" />
          <div className="mt-1 text-[10px] text-white/30">Sell-ордера выше текущей цены. 0 = только покупки</div>
        </div>
        <div>
          <Input value={form.levels_below} onChange={(event) => setForm({ ...form, levels_below: event.target.value })} placeholder="Levels below" />
          <div className="mt-1 text-[10px] text-white/30">Buy-ордера ниже текущей цены. Больше = шире покрытие</div>
        </div>
        <div>
          <Input value={form.rebuild_timeout_sec} onChange={(event) => setForm({ ...form, rebuild_timeout_sec: event.target.value })} placeholder="Rebuild timeout (сек)" />
          <div className="mt-1 text-[10px] text-white/30">Через сколько секунд пересобрать сетку при выходе цены за границу</div>
        </div>
        <div>
          <Input value={form.auto_convert_to} onChange={(event) => setForm({ ...form, auto_convert_to: event.target.value })} placeholder="Авто-конвертация прибыли (напр. USDC)" />
          <div className="mt-1 text-[10px] text-white/30">Валюта для автоматического вывода прибыли. Пусто = не конвертировать</div>
        </div>
      </div>
      {isAdaptive && (
        <>
          <h2 className="text-lg font-semibold">Адаптивные параметры</h2>
          <div>
            <Input value={form.adaptive_timer_sec} onChange={(event) => setForm({ ...form, adaptive_timer_sec: event.target.value })} placeholder="Таймер адаптации (сек)" />
            <div className="mt-1 text-[10px] text-white/30">Минимальный интервал между сдвигами подсетки</div>
          </div>
        </>
      )}
      {error && <div className="text-sm text-red-300">{error}</div>}
      <Button onClick={submit}>Создать</Button>
    </Card>
  );
}
