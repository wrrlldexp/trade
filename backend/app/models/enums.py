"""Перечисления, используемые в моделях БД."""

import enum


class UserRole(str, enum.Enum):
    ULTRAADMIN = "ultraadmin"
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    VIEWER = "viewer"


class GridMode(str, enum.Enum):
    """Режим торговли сетки."""

    PAPER = "paper"
    LIVE = "live"


class GridStatus(str, enum.Enum):
    DRAFT = "draft"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class StrategyType(str, enum.Enum):
    """Тип стратегии (из legacy MoneyBot v1)."""

    SIMPLE = "simple"                           # 1 — фиксированный лот
    CAPITALIZATION = "capitalization"            # 2 — реинвестирование прибыли в лот
    REVERSE = "reverse"                         # 3 — расчёт прибыли через price ratio
    REVERSE_CAPITALIZATION = "reverse_cap"      # 4 — реверс + реинвестирование
    ADAPTIVE = "adaptive"                       # 5 — скользящая подсетка с prepay
    ADAPTIVE_CAPITALIZATION = "adaptive_cap"    # 6 — адаптивная + реинвестирование


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"     # ещё не отправлен на биржу
    PLACED = "placed"       # размещён, ждёт исполнения
    FILLED = "filled"       # исполнен
    CANCELLED = "cancelled"
    WAIT = "wait"           # ожидает (вне адаптивной подсетки)
    ERROR = "error"


class TradeEventType(str, enum.Enum):
    PLACED = "placed"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FLIPPED = "flipped"     # ордер перевернулся (buy → sell или наоборот)
    GRID_REBUILT = "grid_rebuilt"
    ADAPTIVE_SHIFT = "adaptive_shift"  # подсетка сдвинулась


class LogLevel(str, enum.Enum):
    """Уровень логирования бота."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
