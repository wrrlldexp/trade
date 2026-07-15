import { apiClient } from "./client";
import type { Grid, GridOrder, TradeEvent } from "./types";

export async function listGrids() {
  const { data } = await apiClient.get<Grid[]>("/api/grids/");
  return data;
}

export async function createGrid(payload: Record<string, unknown>) {
  const { data } = await apiClient.post<Grid>("/api/grids/", payload);
  return data;
}

export async function getGrid(gridId: string) {
  const { data } = await apiClient.get<Grid & { orders: GridOrder[] }>(`/api/grids/${gridId}`);
  return data;
}

export async function startGrid(gridId: string) {
  const { data } = await apiClient.post<Grid>(`/api/grids/${gridId}/start`);
  return data;
}

export async function stopGrid(gridId: string) {
  const { data } = await apiClient.post<Grid>(`/api/grids/${gridId}/stop`);
  return data;
}

export async function updateGrid(gridId: string, payload: Record<string, unknown>) {
  const { data } = await apiClient.patch<Grid>(`/api/grids/${gridId}`, payload);
  return data;
}

export async function deleteGrid(gridId: string) {
  const { data } = await apiClient.delete<{ success: boolean }>(`/api/grids/${gridId}`);
  return data;
}

export async function listGridOrders(gridId: string) {
  const { data } = await apiClient.get<GridOrder[]>(`/api/grids/${gridId}/orders`);
  return data;
}

export async function listGridEvents(gridId: string) {
  const { data } = await apiClient.get<TradeEvent[]>(`/api/grids/${gridId}/events`);
  return data;
}

export interface GridChartsData {
  grid_id: string;
  grid_name: string;
  symbol: string;
  start_amount: number;
  hours: number;
  points: number;
  price: { t: string; bid: number; ask: number; mid: number }[];
  pnl: { t: string; pnl: number }[];
  equity: { t: string; equity: number }[];
  drawdown: { t: string; drawdown_pct: number; equity: number }[];
  fills: { t: string; side: string; price: number; profit: number; realized_pnl: number }[];
}

export async function fetchGridCharts(gridId: string, hours = 24) {
  const { data } = await apiClient.get<GridChartsData>(`/api/grids/${gridId}/charts?hours=${hours}`);
  return data;
}
