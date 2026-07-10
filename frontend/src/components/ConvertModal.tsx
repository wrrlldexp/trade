import { useState, useEffect, useMemo, useCallback } from "react";
import { ArrowDownUp, Search, Loader2, Check, AlertCircle } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchMarkets, convertCurrency } from "../api/accounts";
import type { CurrencyBalance } from "../api/dashboard";
import { Modal } from "./Modal";
import { Button } from "./Button";

interface ConvertModalProps {
  open: boolean;
  onClose: () => void;
  accountId: string;
  currencies: CurrencyBalance[];
}

type Step = "form" | "confirm" | "success" | "error";

export function ConvertModal({ open, onClose, accountId, currencies }: ConvertModalProps) {
  const queryClient = useQueryClient();

  const [fromCurrency, setFromCurrency] = useState("");
  const [toCurrency, setToCurrency] = useState("");
  const [amount, setAmount] = useState("");
  const [search, setSearch] = useState("");
  const [selectingField, setSelectingField] = useState<"from" | "to" | null>(null);
  const [step, setStep] = useState<Step>("form");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ filled: number; cost: number; average_price: number } | null>(null);
  const [error, setError] = useState("");

  // Загружаем маркеты для определения доступных пар
  const { data: markets } = useQuery({
    queryKey: ["markets", accountId],
    queryFn: () => fetchMarkets(accountId),
    enabled: open && !!accountId,
    staleTime: 5 * 60_000,
  });

  // Собираем уникальный список всех валют из маркетов
  const allCurrencies = useMemo(() => {
    if (!markets) return [];
    const set = new Set<string>();
    for (const m of markets) {
      set.add(m.base);
      set.add(m.quote);
    }
    return Array.from(set).sort();
  }, [markets]);

  // Фильтруем валюты по поиску
  const filteredCurrencies = useMemo(() => {
    const q = search.toUpperCase();
    return allCurrencies.filter((c) => c.includes(q));
  }, [allCurrencies, search]);

  // Проверяем существует ли пара
  const pairExists = useMemo(() => {
    if (!markets || !fromCurrency || !toCurrency) return false;
    const direct = `${fromCurrency}/${toCurrency}`;
    const reverse = `${toCurrency}/${fromCurrency}`;
    return markets.some((m) => m.symbol === direct || m.symbol === reverse);
  }, [markets, fromCurrency, toCurrency]);

  // Баланс выбранной from валюты
  const fromBalance = useMemo(() => {
    const c = currencies.find((c) => c.currency === fromCurrency);
    return c ? Number(c.free) : 0;
  }, [currencies, fromCurrency]);

  const handleSelect = useCallback((currency: string) => {
    if (selectingField === "from") {
      setFromCurrency(currency);
    } else if (selectingField === "to") {
      setToCurrency(currency);
    }
    setSelectingField(null);
    setSearch("");
  }, [selectingField]);

  const handleSwap = () => {
    setFromCurrency(toCurrency);
    setToCurrency(fromCurrency);
    setAmount("");
  };

  const handleMax = () => {
    setAmount(String(fromBalance));
  };

  const handleConfirm = () => {
    if (!fromCurrency || !toCurrency || !amount || Number(amount) <= 0) return;
    setStep("confirm");
  };

  const handleExecute = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await convertCurrency(accountId, fromCurrency, toCurrency, Number(amount));
      setResult({ filled: res.filled, cost: res.cost, average_price: res.average_price });
      setStep("success");
      // Обновляем балансы
      queryClient.invalidateQueries({ queryKey: ["balances"] });
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Ошибка конвертации";
      setError(msg);
      setStep("error");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setStep("form");
    setFromCurrency("");
    setToCurrency("");
    setAmount("");
    setSearch("");
    setSelectingField(null);
    setResult(null);
    setError("");
    onClose();
  };

  // Reset on open
  useEffect(() => {
    if (open) {
      setStep("form");
      setResult(null);
      setError("");
    }
  }, [open]);

  if (!open) return null;

  return (
    <Modal open={open} title="Конвертация" onClose={handleClose}>
      {/* Выбор валюты из списка */}
      {selectingField && (
        <div className="space-y-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск валюты..."
              autoFocus
              className="w-full rounded-xl border border-white/10 bg-white/5 py-2.5 pl-9 pr-3 text-sm text-white placeholder-white/30 outline-none focus:border-indigo-400/50"
            />
          </div>
          <div className="max-h-64 space-y-0.5 overflow-y-auto rounded-xl">
            {filteredCurrencies.map((c) => {
              const bal = currencies.find((cb) => cb.currency === c);
              const balStr = bal ? Number(bal.free).toFixed(bal.currency === "USDT" ? 2 : 6) : null;
              return (
                <button
                  key={c}
                  onClick={() => handleSelect(c)}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm hover:bg-white/10 transition"
                >
                  <span className="font-medium">{c}</span>
                  {balStr && <span className="text-xs text-white/40">{balStr}</span>}
                </button>
              );
            })}
            {filteredCurrencies.length === 0 && (
              <div className="py-4 text-center text-sm text-white/40">Ничего не найдено</div>
            )}
          </div>
          <Button onClick={() => { setSelectingField(null); setSearch(""); }} className="w-full">
            Назад
          </Button>
        </div>
      )}

      {/* Форма конвертации */}
      {!selectingField && step === "form" && (
        <div className="space-y-4">
          {/* FROM */}
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
            <div className="mb-1 text-xs text-white/50">Отдаю</div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSelectingField("from")}
                className="shrink-0 rounded-xl border border-white/10 bg-white/10 px-3 py-2 text-sm font-medium hover:bg-white/15 transition min-w-[80px]"
              >
                {fromCurrency || "Выбрать"}
              </button>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="w-full bg-transparent text-right text-lg font-semibold text-white outline-none placeholder-white/20"
              />
            </div>
            {fromCurrency && (
              <div className="mt-1.5 flex items-center justify-between text-xs text-white/40">
                <span>Доступно: {fromBalance}</span>
                <button onClick={handleMax} className="text-indigo-400 hover:text-indigo-300">MAX</button>
              </div>
            )}
          </div>

          {/* Swap button */}
          <div className="flex justify-center">
            <button
              onClick={handleSwap}
              className="rounded-full border border-white/10 bg-white/5 p-2 hover:bg-white/10 transition"
            >
              <ArrowDownUp size={18} className="text-indigo-400" />
            </button>
          </div>

          {/* TO */}
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
            <div className="mb-1 text-xs text-white/50">Получаю</div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSelectingField("to")}
                className="shrink-0 rounded-xl border border-white/10 bg-white/10 px-3 py-2 text-sm font-medium hover:bg-white/15 transition min-w-[80px]"
              >
                {toCurrency || "Выбрать"}
              </button>
              <div className="w-full text-right text-sm text-white/40">
                по рыночной цене
              </div>
            </div>
          </div>

          {/* Warning if pair doesn't exist */}
          {fromCurrency && toCurrency && !pairExists && (
            <div className="flex items-center gap-2 rounded-xl bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
              <AlertCircle size={14} />
              Нет прямой пары {fromCurrency}/{toCurrency}. Попробуйте через USDT.
            </div>
          )}

          <Button
            onClick={handleConfirm}
            disabled={!fromCurrency || !toCurrency || !amount || Number(amount) <= 0 || !pairExists}
            className="w-full bg-indigo-500/20 text-indigo-200 hover:bg-indigo-500/30 border-indigo-400/20"
          >
            Конвертировать
          </Button>
        </div>
      )}

      {/* Подтверждение */}
      {step === "confirm" && (
        <div className="space-y-4">
          <div className="rounded-2xl bg-white/5 p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-white/50">Отдаю</span>
              <span className="font-semibold">{amount} {fromCurrency}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-white/50">Получаю</span>
              <span className="font-semibold">{toCurrency} (по рынку)</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-white/50">Тип ордера</span>
              <span>Market</span>
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => setStep("form")} className="flex-1">
              Назад
            </Button>
            <Button
              onClick={handleExecute}
              disabled={loading}
              className="flex-1 bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30 border-emerald-400/20"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 size={14} className="animate-spin" />
                  Выполняю...
                </span>
              ) : (
                "Подтвердить"
              )}
            </Button>
          </div>
        </div>
      )}

      {/* Успех */}
      {step === "success" && result && (
        <div className="space-y-4">
          <div className="flex flex-col items-center gap-2 py-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/20">
              <Check size={24} className="text-emerald-400" />
            </div>
            <div className="text-lg font-semibold text-emerald-400">Конвертация выполнена</div>
          </div>
          <div className="rounded-2xl bg-white/5 p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-white/50">Исполнено</span>
              <span>{result.filled}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-white/50">Стоимость</span>
              <span>{result.cost}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-white/50">Средняя цена</span>
              <span>{result.average_price}</span>
            </div>
          </div>
          <Button onClick={handleClose} className="w-full">
            Закрыть
          </Button>
        </div>
      )}

      {/* Ошибка */}
      {step === "error" && (
        <div className="space-y-4">
          <div className="flex flex-col items-center gap-2 py-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-500/20">
              <AlertCircle size={24} className="text-red-400" />
            </div>
            <div className="text-lg font-semibold text-red-400">Ошибка</div>
            <div className="text-sm text-white/60 text-center">{error}</div>
          </div>
          <Button onClick={() => setStep("form")} className="w-full">
            Попробовать снова
          </Button>
        </div>
      )}
    </Modal>
  );
}
