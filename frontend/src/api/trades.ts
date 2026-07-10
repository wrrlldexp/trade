import { apiClient } from "./client";
import type { TradeEventEnriched } from "./types";

export interface TradeFilters {
  grid_id?: string;
  event_type?: string;
  date_from?: string;
  date_to?: string;
  offset?: number;
  limit?: number;
}

export async function listTrades(filters: TradeFilters = {}): Promise<TradeEventEnriched[]> {
  const { data } = await apiClient.get<TradeEventEnriched[]>("/api/trades/", { params: filters });
  return data;
}
