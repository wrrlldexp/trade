import { useQuery } from "@tanstack/react-query";
import { Activity, HardDrive, Cpu, MemoryStick, RefreshCw } from "lucide-react";

import { apiClient } from "../api/client";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";

interface HealthCheck {
  name: string;
  status: "ok" | "warning" | "critical";
  detail: string;
}

interface HealthReport {
  ok: boolean;
  checks: HealthCheck[];
  alerts: string[];
}

async function fetchHealthCheck(): Promise<HealthReport> {
  const { data } = await apiClient.get<HealthReport>("/api/bot/health-check");
  return data;
}

const STATUS_TONE: Record<string, "good" | "warn" | "error" | "neutral"> = {
  ok: "good",
  warning: "warn",
  critical: "error",
};

const CHECK_ICON: Record<string, typeof Activity> = {
  disk: HardDrive,
  memory: MemoryStick,
  cpu: Cpu,
};

const CHECK_LABEL: Record<string, string> = {
  disk: "Диск",
  memory: "Память",
  cpu: "Процессор",
};

export function MonitoringPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["health-check"],
    queryFn: fetchHealthCheck,
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Мониторинг</h1>
            <p className="mt-1 text-sm text-hint">Состояние сервера и сервисов</p>
          </div>
          <Button onClick={() => void refetch()} disabled={isLoading}>
            <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
            Обновить
          </Button>
        </div>
      </Card>

      {data && (
        <>
          <Card>
            <div className="mb-3 flex items-center gap-3">
              <div className={`h-4 w-4 rounded-full ${data.ok ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]" : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.5)]"}`} />
              <h2 className="text-lg font-semibold">
                {data.ok ? "Система в норме" : "Обнаружены проблемы"}
              </h2>
            </div>

            <div className="space-y-3">
              {data.checks.map((check) => {
                const Icon = CHECK_ICON[check.name] || Activity;
                return (
                  <div
                    key={check.name}
                    className="flex items-center justify-between rounded-2xl bg-white/5 p-4"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/15">
                        <Icon size={20} className="text-indigo-400" />
                      </div>
                      <div>
                        <div className="text-sm font-medium">
                          {CHECK_LABEL[check.name] || check.name}
                        </div>
                        <div className="text-xs text-hint">{check.detail}</div>
                      </div>
                    </div>
                    <Badge tone={STATUS_TONE[check.status] || "neutral"}>
                      {check.status === "ok" ? "OK" : check.status === "warning" ? "Внимание" : "Критично"}
                    </Badge>
                  </div>
                );
              })}
            </div>
          </Card>

          {data.alerts.length > 0 && (
            <Card>
              <h2 className="mb-3 text-lg font-semibold text-red-300">Алерты</h2>
              <div className="space-y-2">
                {data.alerts.map((alert, i) => (
                  <div
                    key={i}
                    className="rounded-xl bg-red-400/10 p-3 text-sm text-red-200"
                  >
                    {alert}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}

      <Card>
        <h2 className="mb-3 text-lg font-semibold">Автомониторинг</h2>
        <div className="space-y-2 text-sm text-hint">
          <p>Cron-скрипт проверяет систему каждые 5 минут:</p>
          <ul className="ml-4 list-disc space-y-1">
            <li>Docker-контейнеры запущены (автоперезапуск упавших)</li>
            <li>Backend отвечает на /health</li>
            <li>Диск заполнен {"<"} 80%</li>
            <li>RAM {"<"} 85%</li>
          </ul>
          <p className="mt-3">Ежедневная очистка в 04:00:</p>
          <ul className="ml-4 list-disc space-y-1">
            <li>Docker-мусор (образы, volumes)</li>
            <li>Старые bot_logs ({">"} 30 дней)</li>
            <li>Старые audit_logs ({">"} 90 дней)</li>
          </ul>
        </div>
      </Card>
    </div>
  );
}
