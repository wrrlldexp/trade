import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { useState } from "react";

import { createAccount, deleteAccount, listAccounts, testAccount } from "../api/accounts";
import { useAuthStore } from "../store/auth";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Empty } from "../components/Empty";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { useToast } from "../components/Toast";

export function AccountsPage() {
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((state) => state.user);
  const canManage = currentUser?.role === "admin" || currentUser?.role === "superadmin" || currentUser?.role === "ultraadmin";
  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: listAccounts });
  const { toast } = useToast();
  const [form, setForm] = useState<{
    name: string;
    exchange: "binance" | "bybit";
    api_key: string;
    api_secret: string;
    is_testnet: boolean;
  }>({
    name: "Binance Testnet",
    exchange: "binance",
    api_key: "",
    api_secret: "",
    is_testnet: true,
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["accounts"] });

  return (
    <div className="space-y-5">
      {canManage && (
        <Card className="space-y-3">
          <h1 className="text-2xl font-bold">Биржевые аккаунты</h1>
          <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Название" />
          <Select value={form.exchange} onChange={(event) => setForm({ ...form, exchange: event.target.value as "binance" | "bybit" })}>
            <option value="binance">Binance</option>
            <option value="bybit">Bybit</option>
          </Select>
          <Input value={form.api_key} onChange={(event) => setForm({ ...form, api_key: event.target.value })} placeholder="API key" />
          <Input type="password" value={form.api_secret} onChange={(event) => setForm({ ...form, api_secret: event.target.value })} placeholder="API secret" />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_testnet}
              onChange={(event) => setForm({ ...form, is_testnet: event.target.checked })}
              className="h-4 w-4 rounded border-white/20 bg-white/5"
            />
            Тестовая сеть (Testnet)
          </label>
          <Button
            onClick={async () => {
              try {
                await createAccount(form);
                refresh();
                toast("Аккаунт добавлен", "success");
              } catch {
                toast("Ошибка при добавлении аккаунта", "error");
              }
            }}
          >
            Добавить аккаунт
          </Button>
        </Card>
      )}
      {!canManage && <h1 className="text-2xl font-bold">Биржевые аккаунты</h1>}
      <Card className="space-y-3">
        {accounts.length === 0 && (
          <Empty icon={ClipboardList} title="Аккаунтов нет" description="Добавьте биржевой аккаунт для начала торговли" />
        )}
        {accounts.map((account) => (
          <div key={account.id} className="flex flex-col gap-3 rounded-2xl bg-secondary p-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="font-semibold">{account.name}</div>
              <div className="text-sm text-hint">
                {account.exchange} · {account.is_testnet ? "testnet" : "live"}
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                className="bg-secondary text-text"
                onClick={async () => {
                  try {
                    const result = await testAccount(account.id);
                    toast(result.message || "Готово", result.success ? "success" : "error");
                  } catch {
                    toast("Ошибка при тестировании подключения", "error");
                  }
                }}
              >
                Тест
              </Button>
              {canManage && (
                <Button
                  onClick={async () => {
                    try {
                      await deleteAccount(account.id);
                      refresh();
                      toast("Аккаунт удалён", "success");
                    } catch {
                      toast("Ошибка при удалении аккаунта", "error");
                    }
                  }}
                >
                  Удалить
                </Button>
              )}
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}
