import { useQuery } from "@tanstack/react-query";
import { ArrowLeftRight } from "lucide-react";
import { useState } from "react";

import { listTrades } from "../api/trades";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Empty } from "../components/Empty";
import { Select } from "../components/Select";
import { Spinner } from "../components/Spinner";

const EVENT_LABELS: Record<string, string> = {
  placed: "Размещён",
  filled: "Исполнен",
  cancelled: "Отменён",
  flipped: "Перевёрнут",
  grid_rebuilt: "Перестройка",
  adaptive_shift: "Адаптивный сдвиг",
};

const EVENT_TONE: Record<string, "neutral" | "good" | "warn" | "error"> = {
  placed: "neutral",
  filled: "good",
  cancelled: "warn",
  flipped: "warn",
  grid_rebuilt: "warn",
  adaptive_shift: "neutral",
};

export function TradesPage() {
  const [filterType, setFilterType] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data: trades = [], isLoading } = useQuery({
    queryKey: ["trades", filterType, offset],
    queryFn: () =>
      listTrades({
        event_type: filterType || undefined,
        offset,
        limit,
      }),
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-5">
      <Card>
        <h1 className="mb-4 text-2xl font-bold">Сделки</h1>
        <div className="flex flex-wrap gap-3">
          <Select
            className="w-auto min-w-[140px]"
            value={filterType}
            onChange={(e) => {
              setFilterType(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">Все типы</option>
            <option value="filled">Исполнен</option>
            <option value="placed">Размещён</option>
            <option value="cancelled">Отменён</option>
            <option value="flipped">Перевёрнут</option>
            <option value="grid_rebuilt">Перестройка</option>
            <option value="adaptive_shift">Адаптивный сдвиг</option>
          </Select>
        </div>
      </Card>

      <Card>
        {isLoading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : trades.length === 0 ? (
          <Empty icon={ArrowLeftRight} title="Сделок пока нет" description="Здесь появятся события по торговым сеткам" />
        ) : (
          <>
            <div className="overflow-x-auto -mx-4 sm:-mx-5">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-hint">
                    <th className="pb-3 pl-4 sm:pl-5 pr-4">Время</th>
                    <th className="pb-3 pr-4">Сетка</th>
                    <th className="pb-3 pr-4 hidden sm:table-cell">Пара</th>
                    <th className="pb-3 pr-4">Тип</th>
                    <th className="pb-3 pr-4 hidden sm:table-cell">Цена</th>
                    <th className="pb-3 pr-4 hidden sm:table-cell">Объём</th>
                    <th className="pb-3 pr-4 sm:pr-5">PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => (
                    <tr key={trade.id} className="border-b border-white/5">
                      <td className="py-3 pl-4 sm:pl-5 pr-4 text-xs text-hint whitespace-nowrap">
                        {new Date(trade.created_at).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td className="py-3 pr-4 font-medium">{trade.grid_name}</td>
                      <td className="py-3 pr-4 hidden sm:table-cell">{trade.symbol}</td>
                      <td className="py-3 pr-4">
                        <Badge tone={EVENT_TONE[trade.event_type] ?? "neutral"}>
                          {EVENT_LABELS[trade.event_type] ?? trade.event_type}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 font-mono hidden sm:table-cell">{trade.price ?? "—"}</td>
                      <td className="py-3 pr-4 font-mono hidden sm:table-cell">{trade.amount ?? "—"}</td>
                      <td className="py-3 pr-4 sm:pr-5 font-mono">
                        {trade.pnl_delta ? (
                          <span className={Number(trade.pnl_delta) >= 0 ? "text-emerald-300" : "text-red-300"}>
                            {Number(trade.pnl_delta) >= 0 ? "+" : ""}
                            {trade.pnl_delta}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 flex items-center justify-between">
              <Button
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
              >
                Назад
              </Button>
              <Button
                onClick={() => setOffset(offset + limit)}
                disabled={trades.length < limit}
              >
                Далее
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
