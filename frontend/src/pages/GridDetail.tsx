import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useState } from "react";

import { deleteGrid, getGrid, listGridEvents, startGrid, stopGrid, updateGrid } from "../api/grids";
import { useGridEvents } from "../api/ws";
import { useAuthStore } from "../store/auth";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { Modal } from "../components/Modal";
import { Spinner } from "../components/Spinner";
import { useToast } from "../components/Toast";

const STRATEGY_LABELS: Record<string, string> = {
  simple: "Простая",
  capitalization: "Капитализация",
  reverse: "Реверс",
  reverse_cap: "Реверс + Капитализация",
  adaptive: "Адаптивная",
  adaptive_cap: "Адаптивная + Капитализация",
};

// Параметры для hot-update (можно менять на работающей сетке)
const HOT_PARAMS = ["name", "lot_size", "lot_quote", "profit_step", "rebuild_timeout_sec", "adaptive_timer_sec", "auto_convert_to"];

interface EditForm {
  name: string;
  lot_size: string;
  lot_quote: string;
  profit_step: string;
  grid_step: string;
  levels_above: string;
  levels_below: string;
  rebuild_timeout_sec: string;
  adaptive_timer_sec: string;
  auto_convert_to: string;
}

export function GridDetailPage() {
  const { gridId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: grid } = useQuery({ queryKey: ["grid", gridId], queryFn: () => getGrid(gridId) });
  const { data: events = [] } = useQuery({ queryKey: ["grid-events", gridId], queryFn: () => listGridEvents(gridId) });
  const liveMessages = useGridEvents(gridId);

  const [error, setError] = useState("");
  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const currentUser = useAuthStore((state) => state.user);
  const canManage = currentUser?.role === "admin" || currentUser?.role === "superadmin" || currentUser?.role === "ultraadmin";
  const { toast } = useToast();

  if (!grid) return <div className="flex justify-center py-16"><Spinner /></div>;

  const isRunning = grid.status === "running";
  const isAdaptive = grid.strategy === "adaptive" || grid.strategy === "adaptive_cap";

  const chartData = events
    .slice()
    .reverse()
    .map((event, index) => ({
      index,
      pnl: Number(event.pnl_delta || 0),
    }));

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["grid", gridId] });
    void queryClient.invalidateQueries({ queryKey: ["grid-events", gridId] });
    void queryClient.invalidateQueries({ queryKey: ["grids"] });
  };

  const openEdit = () => {
    setEditForm({
      name: grid.name,
      lot_size: String(grid.lot_size),
      lot_quote: grid.lot_quote ? String(grid.lot_quote) : "",
      profit_step: String(grid.profit_step),
      grid_step: String(grid.grid_step),
      levels_above: String(grid.levels_above),
      levels_below: String(grid.levels_below),
      rebuild_timeout_sec: String(grid.rebuild_timeout_sec),
      adaptive_timer_sec: String(grid.adaptive_timer_sec ?? 15),
      auto_convert_to: grid.auto_convert_to ?? "",
    });
    setShowEdit(true);
  };

  const handleSave = async () => {
    if (!editForm) return;
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {};
      if (editForm.name !== grid.name) payload.name = editForm.name;
      if (editForm.lot_size !== String(grid.lot_size)) payload.lot_size = editForm.lot_size;
      if (editForm.lot_quote !== (grid.lot_quote ? String(grid.lot_quote) : "")) payload.lot_quote = editForm.lot_quote || null;
      if (editForm.profit_step !== String(grid.profit_step)) payload.profit_step = editForm.profit_step;
      if (editForm.grid_step !== String(grid.grid_step)) payload.grid_step = editForm.grid_step;
      if (editForm.levels_above !== String(grid.levels_above)) payload.levels_above = Number(editForm.levels_above);
      if (editForm.levels_below !== String(grid.levels_below)) payload.levels_below = Number(editForm.levels_below);
      if (editForm.rebuild_timeout_sec !== String(grid.rebuild_timeout_sec)) payload.rebuild_timeout_sec = Number(editForm.rebuild_timeout_sec);
      if (editForm.adaptive_timer_sec !== String(grid.adaptive_timer_sec ?? 15)) payload.adaptive_timer_sec = Number(editForm.adaptive_timer_sec);
      if (editForm.auto_convert_to !== (grid.auto_convert_to ?? "")) payload.auto_convert_to = editForm.auto_convert_to || null;

      if (Object.keys(payload).length === 0) {
        setShowEdit(false);
        return;
      }
      await updateGrid(grid.id, payload);
      setShowEdit(false);
      refresh();
      toast("Настройки сохранены", "success");
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Ошибка при сохранении");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Удалить сетку? Все ордеры и история будут удалены безвозвратно.")) return;
    setDeleting(true);
    setError("");
    try {
      if (isRunning) {
        await stopGrid(grid.id);
      }
      await deleteGrid(grid.id);
      void queryClient.invalidateQueries({ queryKey: ["grids"] });
      navigate("/grids");
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Ошибка при удалении");
    } finally {
      setDeleting(false);
    }
  };

  const isFieldDisabled = (field: string) => isRunning && !HOT_PARAMS.includes(field);

  return (
    <div className="space-y-5">
      <Card className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-2xl font-bold">{grid.name}</div>
          <div className="text-sm text-hint">
            {grid.symbol} · {grid.mode === "live" ? "Боевой" : "Бумажный"} · {STRATEGY_LABELS[grid.strategy] || grid.strategy}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge tone={grid.status === "running" ? "good" : "neutral"}>
            {grid.status === "running" ? "Работает" : grid.status === "stopped" ? "Остановлена" : grid.status === "draft" ? "Черновик" : grid.status === "error" ? "Ошибка" : grid.status}
          </Badge>
          {canManage && (
            <>
              <Button
                loading={toggling}
                disabled={toggling}
                onClick={async () => {
                  setToggling(true);
                  try {
                    setError("");
                    if (isRunning) {
                      await stopGrid(grid.id);
                      toast("Сетка остановлена", "info");
                    } else {
                      await startGrid(grid.id);
                      toast("Сетка запущена", "success");
                    }
                    refresh();
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Ошибка при управлении сеткой");
                  } finally {
                    setToggling(false);
                  }
                }}
              >
                {isRunning ? "Стоп" : "Запуск"}
              </Button>
              <Button className="bg-white/5 text-white/70 hover:bg-white/10" onClick={openEdit}>
                Настроить
              </Button>
              <Button className="bg-red-500/10 text-red-300 hover:bg-red-500/20" onClick={handleDelete} loading={deleting} disabled={deleting}>
                Удалить
              </Button>
            </>
          )}
        </div>
      </Card>
      {error && <div className="rounded-2xl bg-red-500/10 p-3 text-sm text-red-300">{error}</div>}

      {/* Параметры сетки */}
      <Card>
        <h2 className="mb-3 text-lg font-semibold">Параметры</h2>
        <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-xl bg-white/5 p-3">
            <div className="text-xs text-white/40">Лот</div>
            <div className="mt-1 font-medium">
              {grid.lot_quote ? <>{grid.lot_quote} <span className="text-white/40">USDT</span></> : grid.lot_size}
            </div>
            <div className="mt-1 text-[10px] text-white/30">
              {grid.lot_quote ? "Фиксированная сумма в USDT, пересчёт по курсу" : "Фиксированный объём в базовой валюте"}
            </div>
          </div>
          <div className="rounded-xl bg-white/5 p-3">
            <div className="text-xs text-white/40">Шаг профита</div>
            <div className="mt-1 font-medium">{grid.profit_step}</div>
            <div className="mt-1 text-[10px] text-white/30">Разница между buy и sell ценой = ваша прибыль</div>
          </div>
          <div className="rounded-xl bg-white/5 p-3">
            <div className="text-xs text-white/40">Шаг сетки</div>
            <div className="mt-1 font-medium">{grid.grid_step}</div>
            <div className="mt-1 text-[10px] text-white/30">Расстояние между уровнями ордеров</div>
          </div>
          <div className="rounded-xl bg-white/5 p-3">
            <div className="text-xs text-white/40">Уровни</div>
            <div className="mt-1 font-medium">{grid.levels_above} вверх / {grid.levels_below} вниз</div>
            <div className="mt-1 text-[10px] text-white/30">Количество ордеров выше и ниже центра</div>
          </div>
          <div className="rounded-xl bg-white/5 p-3">
            <div className="text-xs text-white/40">Таймаут перестройки</div>
            <div className="mt-1 font-medium">{grid.rebuild_timeout_sec} сек</div>
            <div className="mt-1 text-[10px] text-white/30">Через сколько пересобрать сетку при выходе цены за диапазон</div>
          </div>
          <div className="rounded-xl bg-white/5 p-3">
            <div className="text-xs text-white/40">Авто-конвертация прибыли</div>
            <div className="mt-1 font-medium">{grid.auto_convert_to || "Выключена"}</div>
            {grid.auto_convert_to && Number(grid.unconverted_pnl) > 0 && (
              <div className="mt-1 text-[10px] text-amber-300">Накоплено: {grid.unconverted_pnl} (конвертация от $1.10)</div>
            )}
            <div className="mt-1 text-[10px] text-white/30">Прибыль автоматически переводится в указанную валюту</div>
          </div>
          {isAdaptive && (
              <div className="rounded-xl bg-white/5 p-3">
                <div className="text-xs text-white/40">Таймер адаптации</div>
                <div className="mt-1 font-medium">{grid.adaptive_timer_sec} сек</div>
                <div className="mt-1 text-[10px] text-white/30">Минимальный интервал между сдвигами подсетки</div>
              </div>
          )}
        </div>
      </Card>

      <div className={`grid gap-4 ${isAdaptive ? "md:grid-cols-4" : "md:grid-cols-3"}`}>
        <Card>
          <div className="text-sm text-hint">Реализованная прибыль</div>
          <div className="mt-2 text-2xl font-bold">{grid.realized_pnl}</div>
        </Card>
        <Card>
          <div className="text-sm text-hint">Сделки</div>
          <div className="mt-2 text-2xl font-bold">{grid.total_trades}</div>
        </Card>
        <Card>
          <div className="text-sm text-hint">Ордеров</div>
          <div className="mt-2 text-2xl font-bold">{grid.orders?.length ?? 0}</div>
        </Card>
        {isAdaptive && (
          <Card>
            <div className="text-sm text-hint">Подсетка</div>
            <div className="mt-2 text-sm">
              {grid.adaptive_bottom_order_idx ?? "—"} → {grid.adaptive_top_order_idx ?? "—"}
            </div>
          </Card>
        )}
      </div>
      <Card>
        <h2 className="mb-4 text-xl font-semibold">PnL</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <XAxis dataKey="index" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="pnl" stroke="#2481cc" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <h2 className="mb-4 text-xl font-semibold">Ордеры</h2>
        <div className="space-y-2">
          {(grid.orders ?? [])
            .slice()
            .sort((a, b) => a.grid_index - b.grid_index)
            .map((order) => (
              <div key={order.id} className="rounded-2xl bg-secondary p-3 text-sm">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="font-mono text-xs text-hint">#{order.grid_index}</span>
                    <span>
                      {order.side} @ {order.price} → {order.price_sell}
                    </span>
                    <span className="text-xs text-hint">кол-во: {order.amount}</span>
{order.re_buy && <Badge tone="warn">повт.покупка</Badge>}
                    {order.re_sell && <Badge tone="warn">повт.продажа</Badge>}
                    {order.count_complete > 0 && (
                      <span className="text-xs text-hint">циклы: {order.count_complete}</span>
                    )}
                    {Number(order.profit) > 0 && (
                      <span className="text-xs text-hint">прибыль: {order.profit}</span>
                    )}
                  </div>
                  <Badge tone={order.status === "filled" ? "good" : order.status === "wait" ? "warn" : "neutral"}>
                    {order.status === "filled" ? "Исполнен" : order.status === "placed" ? "Размещён" : order.status === "wait" ? "Ожидание" : order.status === "cancelled" ? "Отменён" : order.status === "pending" ? "Подготовка" : order.status === "error" ? "Ошибка" : order.status}
                  </Badge>
                </div>
                <div className="mt-1 flex gap-4 text-xs text-hint">
                  <span>Размещён: {new Date(order.created_at).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
                  {order.filled_at && (
                    <span>Исполнен: {new Date(order.filled_at).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
                  )}
                </div>
              </div>
            ))}
        </div>
      </Card>
      <Card>
        <h2 className="mb-4 text-xl font-semibold">События в реальном времени</h2>
        <div className="space-y-2 text-xs">
          {liveMessages.map((message, index) => (
            <pre key={index} className="overflow-auto rounded-2xl bg-secondary p-3">
              {message}
            </pre>
          ))}
        </div>
      </Card>

      {/* Edit Modal */}
      {showEdit && editForm && (
        <Modal onClose={() => setShowEdit(false)}>
          <div className="space-y-4">
            <h2 className="text-xl font-bold">
              Настройка сетки
              {isRunning && <span className="ml-2 text-sm font-normal text-emerald-400">(запущена)</span>}
            </h2>
            {isRunning && (
              <div className="rounded-xl bg-amber-400/10 p-3 text-xs text-amber-200">
                Сетка запущена. Доступны: название, лот, шаг профита, таймеры, доплата. Для изменения шага сетки и уровней — остановите сетку.
              </div>
            )}

            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-white/50">Название сетки</label>
                <Input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-white/50">Лот (базовая)</label>
                  <Input value={editForm.lot_size} onChange={(e) => setEditForm({ ...editForm, lot_size: e.target.value })} />
                  <div className="mt-1 text-[10px] text-white/30">Объём в BTC/SOL. Игнорируется если задан «Лот в USDT»</div>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-white/50">Лот в USDT (рекоменд.)</label>
                  <Input value={editForm.lot_quote} onChange={(e) => setEditForm({ ...editForm, lot_quote: e.target.value })} placeholder="напр. 2.5" />
                  <div className="mt-1 text-[10px] text-white/30">Сумма в USDT на ордер. Пересчёт по курсу — защита от утечки</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-white/50">Шаг профита</label>
                  <Input value={editForm.profit_step} onChange={(e) => setEditForm({ ...editForm, profit_step: e.target.value })} />
                  <div className="mt-1 text-[10px] text-white/30">Разница buy/sell = ваша прибыль с каждой сделки</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-white/50">
                    Шаг сетки {isRunning && <span className="text-amber-300">(заблок.)</span>}
                  </label>
                  <Input value={editForm.grid_step} onChange={(e) => setEditForm({ ...editForm, grid_step: e.target.value })} disabled={isFieldDisabled("grid_step")} />
                  <div className="mt-1 text-[10px] text-white/30">Расстояние между уровнями. Меньше = больше сделок, но нужен больше депозит</div>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-white/50">Таймаут перестройки (сек)</label>
                  <Input value={editForm.rebuild_timeout_sec} onChange={(e) => setEditForm({ ...editForm, rebuild_timeout_sec: e.target.value })} />
                  <div className="mt-1 text-[10px] text-white/30">Через сколько секунд пересобрать сетку при выходе цены за границу</div>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs text-white/50">Авто-конвертация прибыли</label>
                <Input value={editForm.auto_convert_to} onChange={(e) => setEditForm({ ...editForm, auto_convert_to: e.target.value })} placeholder="напр. USDC (пусто = выкл)" />
                <div className="mt-1 text-[10px] text-white/30">Прибыль автоматически переводится в указанную валюту при накоплении от $1.10</div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-white/50">
                    Уровней вверх {isRunning && <span className="text-amber-300">(заблок.)</span>}
                  </label>
                  <Input value={editForm.levels_above} onChange={(e) => setEditForm({ ...editForm, levels_above: e.target.value })} disabled={isFieldDisabled("levels_above")} />
                  <div className="mt-1 text-[10px] text-white/30">Sell-ордера выше текущей цены. 0 = только покупки</div>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-white/50">
                    Уровней вниз {isRunning && <span className="text-amber-300">(заблок.)</span>}
                  </label>
                  <Input value={editForm.levels_below} onChange={(e) => setEditForm({ ...editForm, levels_below: e.target.value })} disabled={isFieldDisabled("levels_below")} />
                  <div className="mt-1 text-[10px] text-white/30">Buy-ордера ниже текущей цены. Больше = шире покрытие</div>
                </div>
              </div>
              {isAdaptive && (
                <>
                  <h3 className="text-sm font-semibold text-white/70">Адаптивные параметры</h3>
                  <div>
                    <label className="mb-1 block text-xs text-white/50">Таймер адаптации (сек)</label>
                    <Input value={editForm.adaptive_timer_sec} onChange={(e) => setEditForm({ ...editForm, adaptive_timer_sec: e.target.value })} />
                    <div className="mt-1 text-[10px] text-white/30">Минимальный интервал между сдвигами подсетки</div>
                  </div>
                </>
              )}
            </div>

            {error && <div className="text-sm text-red-300">{error}</div>}
            <div className="flex gap-3">
              <Button
                className="flex-1 border-transparent bg-gradient-to-r from-indigo-500 to-cyan-400 text-white hover:brightness-110"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? "Сохранение..." : "Сохранить"}
              </Button>
              <Button className="bg-white/5 text-white/70" onClick={() => setShowEdit(false)}>
                Отмена
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
