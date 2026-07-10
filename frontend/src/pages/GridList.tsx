import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { Link } from "react-router-dom";

import { botEmergencyStop } from "../api/bot";
import { deleteGrid, listGrids, stopGrid } from "../api/grids";
import { useAuthStore } from "../store/auth";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Empty } from "../components/Empty";
import { Spinner } from "../components/Spinner";
import { Table } from "../components/Table";
import { useToast } from "../components/Toast";

export function GridListPage() {
  const { data: grids = [], isLoading } = useQuery({ queryKey: ["grids"], queryFn: listGrids });
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((state) => state.user);
  const canManage = currentUser?.role === "admin" || currentUser?.role === "superadmin" || currentUser?.role === "ultraadmin";
  const { toast } = useToast();

  const hasRunning = grids.some((g) => g.status === "running");

  const handleDelete = async (gridId: string, gridName: string, isRunning: boolean) => {
    if (!confirm(`Удалить сетку "${gridName}"? Все ордеры и история будут удалены.`)) return;
    try {
      if (isRunning) await stopGrid(gridId);
      await deleteGrid(gridId);
      void queryClient.invalidateQueries({ queryKey: ["grids"] });
      toast(`Сетка "${gridName}" удалена`, "success");
    } catch {
      toast("Ошибка при удалении сетки", "error");
    }
  };

  const handleEmergencyStop = async () => {
    if (!confirm("АВАРИЙНАЯ ОСТАНОВКА\n\nВсе сетки будут остановлены, ВСЕ ордеры на бирже отменены.\n\nПродолжить?")) return;
    try {
      const result = await botEmergencyStop();
      toast(`Остановлено: ${result.stopped_grids} сеток, ${result.cancelled_orders} ордеров`, "success");
      void queryClient.invalidateQueries({ queryKey: ["grids"] });
    } catch {
      toast("Ошибка аварийной остановки", "error");
    }
  };

  return (
    <Card className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold">Торговые сетки</h1>
        <div className="flex items-center gap-2">
          {canManage && hasRunning && (
            <Button
              onClick={handleEmergencyStop}
              className="flex items-center gap-1.5 border-red-500/40 bg-red-600/20 text-red-100 hover:bg-red-600/30"
            >
              Аварийная остановка
            </Button>
          )}
          {canManage && (
            <Link to="/grids/new">
              <Button>+ Создать сетку</Button>
            </Link>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : grids.length === 0 ? (
        <Empty icon={BarChart3} title="Сеток пока нет" description="Создайте первую торговую сетку">
          {canManage && (
            <Link to="/grids/new"><Button>+ Создать сетку</Button></Link>
          )}
        </Empty>
      ) : (
        <Table>
          <table className="min-w-full text-sm">
            <thead className="bg-secondary text-left">
              <tr>
                <th className="px-4 py-3">Имя</th>
                <th className="px-4 py-3">Пара</th>
                <th className="px-4 py-3 hidden sm:table-cell">Стратегия</th>
                <th className="px-4 py-3 hidden sm:table-cell">Режим</th>
                <th className="px-4 py-3">Статус</th>
                <th className="px-4 py-3">PnL</th>
                {canManage && <th className="px-4 py-3"></th>}
              </tr>
            </thead>
            <tbody>
              {grids.map((grid) => (
                <tr key={grid.id} className="border-t border-secondary">
                  <td className="px-4 py-3">
                    <Link to={`/grids/${grid.id}`} className="text-link underline">
                      {grid.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{grid.symbol}</td>
                  <td className="px-4 py-3 hidden sm:table-cell">{grid.strategy}</td>
                  <td className="px-4 py-3 hidden sm:table-cell">{grid.mode}</td>
                  <td className="px-4 py-3">
                    <Badge tone={grid.status === "running" ? "good" : "neutral"}>{grid.status}</Badge>
                  </td>
                  <td className="px-4 py-3 font-mono">{grid.realized_pnl}</td>
                  {canManage && (
                    <td className="px-4 py-3">
                      <button
                        className="rounded-lg px-2 py-1 text-xs text-red-400 hover:bg-red-400/10 hover:text-red-300 transition-colors"
                        onClick={() => handleDelete(grid.id, grid.name, grid.status === "running")}
                      >
                        Удалить
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </Table>
      )}
    </Card>
  );
}
