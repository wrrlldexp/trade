export type UserRole = "ultraadmin" | "superadmin" | "admin" | "viewer";
export type GridMode = "paper" | "live";
export type GridStatus = "draft" | "running" | "stopped" | "error";
export type StrategyType = "simple" | "capitalization" | "reverse" | "reverse_cap" | "adaptive" | "adaptive_cap";
export type OrderSide = "buy" | "sell";
export type OrderStatus = "pending" | "placed" | "filled" | "cancelled" | "wait" | "error";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  totp_enabled: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginResponse {
  requires_2fa: boolean;
  temporary_token?: string | null;
  tokens?: TokenPair | null;
  user?: User | null;
}

export interface ExchangeAccount {
  id: string;
  owner_id: string;
  name: string;
  exchange: "binance" | "bybit";
  is_testnet: boolean;
  is_active: boolean;
  created_at: string;
}

export interface Grid {
  id: string;
  account_id: string;
  name: string;
  symbol: string;
  mode: GridMode;
  status: GridStatus;
  strategy: StrategyType;
  lot_size: string;
  lot_quote: string | null;
  profit_step: string;
  grid_step: string;
  levels_above: number;
  levels_below: number;
  rebuild_timeout_sec: number;
  last_boundary_hit_at: string | null;
  tick_interval_sec?: number;
  // Статистика
  total_trades: number;
  realized_pnl: string;
  // Авто-конвертация
  auto_convert_to: string | null;
  unconverted_pnl: string;
  created_at: string;
  started_at: string | null;
  stopped_at: string | null;
}

export interface GridOrder {
  id: string;
  grid_index: number;
  side: OrderSide;
  status: OrderStatus;
  price: string;
  price_sell: string;
  amount: string;
  exchange_order_id: string | null;
  profit: string;
  count_complete: number;
  created_at: string;
  filled_at: string | null;
}

export interface TradeEvent {
  id: number;
  event_type: string;
  price: string | null;
  amount: string | null;
  pnl_delta: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export type LogLevel = "info" | "warning" | "error" | "critical";

export interface BotLogTranslation {
  severity: string;
  title: string;
  body: string | null;
  emoji: string;
  cause?: string | null;
  fix?: string | null;
  doc_ref?: string | null;
}

export interface BotLogEntry {
  id: number;
  level: LogLevel;
  message: string;
  source: string | null;
  grid_id: string | null;
  traceback: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
  timestamp?: string;
  translated?: BotLogTranslation | null;
}

export interface BotLogListResponse {
  items: BotLogEntry[];
  total: number;
}

export interface TradeEventEnriched {
  id: number;
  grid_id: string;
  grid_name: string;
  symbol: string;
  event_type: string;
  price: string | null;
  amount: string | null;
  pnl_delta: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}
