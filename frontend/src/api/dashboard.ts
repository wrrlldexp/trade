import { apiClient } from "./client";

export interface StrategyStats {
  strategy: string;
  grids_count: number;
  active_count: number;
  total_pnl: number;
  total_trades: number;
}

export interface PositionSummary {
  grid_id: string;
  grid_name: string;
  symbol: string;
  strategy: string;
  status: string;
  mode: string;
  side: string;
  entry_price: number;
  current_levels: number;
  filled_orders: number;
  realized_pnl: number;
  total_trades: number;
  auto_convert_to: string | null;
  unconverted_pnl: number;
}

export interface DashboardData {
  total_grids: number;
  active_grids: number;
  total_pnl: number;
  total_trades: number;
  win_rate: number;
  strategies: StrategyStats[];
  positions: PositionSummary[];
  equity_curve: { date: string; value: number; label: string }[];
}

export interface CurrencyBalance {
  currency: string;
  total: string;
  free: string;
  used: string;
}

export interface AccountBalance {
  account_id: string;
  name: string;
  exchange: string;
  testnet: boolean;
  currencies: CurrencyBalance[];
  error?: string;
}

export async function fetchDashboard() {
  const { data } = await apiClient.get<DashboardData>("/api/dashboard/");
  return data;
}

export async function fetchBalances() {
  const { data } = await apiClient.get<AccountBalance[]>("/api/accounts/balances");
  return data;
}

// ─── Analytics ───

export interface PnlPoint {
  date: string;
  pnl: number;
  cumulative: number;
}

export interface GridPnlSeries {
  grid_id: string;
  grid_name: string;
  symbol: string;
  strategy: string;
  points: PnlPoint[];
}

export interface DailyActivity {
  date: string;
  trades: number;
  buys: number;
  sells: number;
}

export interface PeriodStats {
  pnl_24h: number;
  pnl_today: number;
  pnl_week: number;
  pnl_month: number;
  trades_24h: number;
  trades_today: number;
  trades_week: number;
  trades_month: number;
  total_loss: number;
  total_profit: number;
  best_trade: number;
  worst_trade: number;
  avg_profit_per_trade: number;
  profit_factor: number;
  win_rate: number;
  total_volume: number;
  max_drawdown: number;
  avg_trade_pnl: number;
  win_streak: number;
  loss_streak: number;
  max_win_streak: number;
  max_loss_streak: number;
  total_commission: number;
  total_rounds: number;
}

export interface HourlyDistribution {
  hour: number;
  trades: number;
  pnl: number;
}

export interface GridComparison {
  grid_id: string;
  grid_name: string;
  symbol: string;
  strategy: string;
  status: string;
  total_trades: number;
  realized_pnl: number;
  win_rate: number;
  avg_profit: number;
  max_drawdown: number;
  profit_factor: number;
  total_volume: number;
  runtime_hours: number;
  total_commission: number;
  total_rounds: number;
  pnl_per_hour: number;
}

export interface DrawdownPoint {
  date: string;
  drawdown: number;
  peak: number;
}

export interface RecentTrade {
  grid_id: string;
  grid_name: string;
  symbol: string;
  event_type: string;
  side: string | null;
  price: number | null;
  amount: number | null;
  pnl_delta: number | null;
  commission: number | null;
  created_at: string;
}

export interface GridAnalytics {
  grid_id: string;
  grid_name: string;
  symbol: string;
  strategy: string;
  status: string;
  period_stats: PeriodStats;
  daily_activity: DailyActivity[];
  hourly_distribution: HourlyDistribution[];
  pnl_series: PnlPoint[];
  drawdown_curve: DrawdownPoint[];
  recent_trades: RecentTrade[];
}

export interface AnalyticsData {
  grids: GridAnalytics[];
  total_stats: PeriodStats;
  total_daily_activity: DailyActivity[];
  grid_comparison: GridComparison[];
  // Legacy compat
  pnl_series: GridPnlSeries[];
  daily_activity: DailyActivity[];
  period_stats: PeriodStats;
  recent_trades: RecentTrade[];
  hourly_distribution: HourlyDistribution[];
  drawdown_curve: DrawdownPoint[];
}

export async function fetchAnalytics(days = 30) {
  const { data } = await apiClient.get<AnalyticsData>(`/api/dashboard/analytics?days=${days}`);
  return data;
}
