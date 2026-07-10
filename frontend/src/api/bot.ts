import { apiClient } from "./client";

export interface BotStatus {
  online: boolean;
  active_grids: number;
  grid_ids: string[];
  last_seen: number | null;
  age_sec?: number;
}

export async function fetchBotStatus(): Promise<BotStatus> {
  const { data } = await apiClient.get<BotStatus>("/api/bot/status");
  return data;
}

export interface EmergencyStopResult {
  detail: string;
  stopped_grids: number;
  cancelled_orders: number;
  errors: string[];
}

export async function botEmergencyStop(): Promise<EmergencyStopResult> {
  const { data } = await apiClient.post<EmergencyStopResult>("/api/bot/emergency-stop");
  return data;
}

export async function botStopAll(): Promise<void> {
  await apiClient.post("/api/bot/stop-all");
}

export async function botRestart(): Promise<void> {
  await apiClient.post("/api/bot/restart");
}
