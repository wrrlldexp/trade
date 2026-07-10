import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listLogs } from "../api/logs";
import type { LogLevel } from "../api/types";
import { useLogStream } from "../api/ws";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { Select } from "../components/Select";

const LEVEL_TONE: Record<LogLevel, "neutral" | "good" | "warn" | "error"> = {
  info: "neutral",
  warning: "warn",
  error: "error",
  critical: "error",
};

const LEVEL_LABEL: Record<LogLevel, string> = {
  info: "ИНФО",
  warning: "ВНИМАНИЕ",
  error: "ОШИБКА",
  critical: "КРИТИЧНО",
};

export function LogsPage() {
  const [filterLevel, setFilterLevel] = useState<LogLevel | "">("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const limit = 50;

  const liveLogs = useLogStream();

  const { data } = useQuery({
    queryKey: ["logs", filterLevel, search, offset],
    queryFn: () =>
      listLogs({
        level: filterLevel || undefined,
        search: search || undefined,
        offset,
        limit,
      }),
    refetchInterval: 10000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-5">
      <Card>
        <h1 className="mb-4 text-2xl font-bold">Логи бота</h1>
        <div className="flex flex-wrap gap-3">
          <Select
            className="w-auto min-w-[140px]"
            value={filterLevel}
            onChange={(e) => {
              setFilterLevel(e.target.value as LogLevel | "");
              setOffset(0);
            }}
          >
            <option value="">Все уровни</option>
            <option value="info">ИНФО</option>
            <option value="warning">ВНИМАНИЕ</option>
            <option value="error">ОШИБКА</option>
            <option value="critical">КРИТИЧНО</option>
          </Select>
          <Input
            className="w-auto min-w-[180px]"
            placeholder="Поиск по тексту..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </div>
      </Card>

      {liveLogs.length > 0 && (
        <Card>
          <h2 className="mb-3 text-lg font-semibold">Real-time</h2>
          <div className="space-y-2">
            {liveLogs.slice(0, 10).map((entry, idx) => (
              <div
                key={`live-${idx}`}
                className="flex items-start gap-3 rounded-2xl bg-secondary p-3 text-sm"
              >
                <Badge tone={LEVEL_TONE[entry.level]}>
                  {LEVEL_LABEL[entry.level]}
                </Badge>
                <div className="min-w-0 flex-1">
                  <div>
                    {entry.translated ? (
                      <span>{entry.translated.emoji} {entry.translated.title}</span>
                    ) : (
                      entry.message
                    )}
                  </div>
                  {entry.translated?.cause && (
                    <div className="mt-1 text-xs text-yellow-300">
                      {entry.translated.cause}
                    </div>
                  )}
                  {entry.source && (
                    <div className="mt-1 font-mono text-xs text-hint">{entry.source}</div>
                  )}
                </div>
                <div className="shrink-0 text-xs text-hint">
                  {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString("ru-RU") : ""}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <h2 className="mb-3 text-lg font-semibold">
          История ({total})
        </h2>
        <div className="space-y-2">
          {items.map((entry) => (
            <div key={entry.id}>
              <button
                type="button"
                className="flex w-full items-start gap-3 rounded-2xl bg-secondary p-3 text-left text-sm"
                onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
              >
                <Badge tone={LEVEL_TONE[entry.level]}>
                  {LEVEL_LABEL[entry.level]}
                </Badge>
                <div className="min-w-0 flex-1">
                  <div>
                    {entry.translated ? (
                      <span>{entry.translated.emoji} {entry.translated.title}</span>
                    ) : (
                      entry.message
                    )}
                  </div>
                  {entry.translated && entry.translated.title !== entry.message && (
                    <div className="mt-1 text-xs text-hint">{entry.message}</div>
                  )}
                  {entry.source && (
                    <div className="mt-1 font-mono text-xs text-hint">{entry.source}</div>
                  )}
                </div>
                <div className="shrink-0 text-xs text-hint">
                  {new Date(entry.created_at).toLocaleString("ru-RU")}
                </div>
              </button>
              {expandedId === entry.id && (
                <div className="ml-4 mt-1 space-y-2 rounded-xl bg-secondary/50 p-3">
                  {entry.translated?.cause && (
                    <div className="rounded-xl bg-yellow-900/20 p-3">
                      <div className="mb-1 text-xs font-semibold text-yellow-300">Причина:</div>
                      <div className="text-sm">{entry.translated.cause}</div>
                      {entry.translated.fix && (
                        <>
                          <div className="mb-1 mt-2 text-xs font-semibold text-green-300">Решение:</div>
                          <div className="text-sm">{entry.translated.fix}</div>
                        </>
                      )}
                    </div>
                  )}
                  {entry.traceback && (
                    <div>
                      <div className="mb-1 text-xs font-semibold text-red-300">Traceback:</div>
                      <pre className="overflow-auto whitespace-pre-wrap rounded-xl bg-secondary p-3 font-mono text-xs">
                        {entry.traceback}
                      </pre>
                    </div>
                  )}
                  {entry.payload && (
                    <div>
                      <div className="mb-1 text-xs font-semibold text-hint">Payload:</div>
                      <pre className="overflow-auto rounded-xl bg-secondary p-3 font-mono text-xs">
                        {JSON.stringify(entry.payload, null, 2)}
                      </pre>
                    </div>
                  )}
                  {entry.grid_id && (
                    <div className="text-xs text-hint">Сетка: {entry.grid_id}</div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
        {items.length > 0 && (
          <div className="mt-4 flex items-center justify-between">
            <Button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
            >
              Назад
            </Button>
            <span className="text-sm text-hint">
              {offset + 1}–{Math.min(offset + limit, total)} из {total}
            </span>
            <Button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
            >
              Далее
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
