import { apiClient } from "./client";
import type { BotLogListResponse, LogLevel } from "./types";

export interface LogFilters {
  level?: LogLevel;
  grid_id?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
  offset?: number;
  limit?: number;
}

export async function listLogs(filters: LogFilters = {}): Promise<BotLogListResponse> {
  const { data } = await apiClient.get<BotLogListResponse>("/api/logs/", { params: filters });
  return data;
}
