import { apiClient } from "./client";
import type { ExchangeAccount } from "./types";

export async function listAccounts() {
  const { data } = await apiClient.get<ExchangeAccount[]>("/api/accounts/");
  return data;
}

export async function createAccount(payload: {
  name: string;
  exchange: "binance" | "bybit";
  api_key: string;
  api_secret: string;
  is_testnet: boolean;
}) {
  const { data } = await apiClient.post<ExchangeAccount>("/api/accounts/", payload);
  return data;
}

export async function deleteAccount(accountId: string) {
  const { data } = await apiClient.delete<{ success: boolean }>(`/api/accounts/${accountId}`);
  return data;
}

export async function testAccount(accountId: string) {
  const { data } = await apiClient.post<{
    success: boolean;
    message: string | null;
    balance: Record<string, string> | null;
    exchange?: "binance" | "bybit" | null;
    testnet?: boolean | null;
    error?: string | null;
  }>(`/api/accounts/${accountId}/test`);
  return data;
}

export interface MarketPair {
  symbol: string;
  base: string;
  quote: string;
}

export async function fetchMarkets(accountId: string, search = "") {
  const { data } = await apiClient.get<MarketPair[]>(
    `/api/accounts/${accountId}/markets`,
    { params: { search } },
  );
  return data;
}

export interface ConvertResult {
  success: boolean;
  order_id: string;
  filled: number;
  cost: number;
  average_price: number;
  from_currency: string;
  to_currency: string;
}

export async function convertCurrency(
  accountId: string,
  from_currency: string,
  to_currency: string,
  amount: number,
) {
  const { data } = await apiClient.post<ConvertResult>(
    `/api/accounts/${accountId}/convert`,
    { from_currency, to_currency, amount },
  );
  return data;
}
