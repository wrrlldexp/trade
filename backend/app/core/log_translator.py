"""LogTranslator — перевод сырых событий бота в человекочитаемые сообщения.

Используется:
- Frontend (лента логов / сделок)
- Telegram-бот (уведомления)
- Obsidian-справочник ошибок

Каждое сообщение имеет severity (info/success/warning/error/critical)
и human-readable текст на русском.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TranslatedMessage:
    """Результат перевода события."""

    severity: str          # info | success | warning | error | critical
    title: str             # короткий заголовок (1 строка)
    body: str | None       # развёрнутое описание (опционально)
    emoji: str             # для Telegram / UI


# ---------------------------------------------------------------------------
# Trade Event translations
# ---------------------------------------------------------------------------

_TRADE_EVENT_MAP: dict[str, tuple[str, str, str]] = {
    # event_type → (severity, emoji, title_template)
    "placed":          ("info",    "📤", "Ордер размещён"),
    "filled":          ("success", "✅", "Ордер исполнен"),
    "cancelled":       ("info",    "🚫", "Ордер отменён"),
    "flipped":         ("success", "🔄", "Ордер перевернулся"),
    "grid_rebuilt":    ("info",    "🔧", "Сетка перестроена"),
    "adaptive_shift":  ("info",    "📐", "Адаптивный сдвиг"),
}


def translate_trade_event(
    event_type: str,
    *,
    grid_name: str | None = None,
    symbol: str | None = None,
    price: str | Decimal | None = None,
    amount: str | Decimal | None = None,
    pnl_delta: str | Decimal | None = None,
    side: str | None = None,
    payload: dict | None = None,
) -> TranslatedMessage:
    """Перевести TradeEvent в человекочитаемое сообщение."""
    severity, emoji, base_title = _TRADE_EVENT_MAP.get(
        event_type, ("info", "📋", f"Событие: {event_type}")
    )

    grid_label = f"[{grid_name}]" if grid_name else ""
    pair_label = f" {symbol}" if symbol else ""

    # Формируем title
    if event_type == "placed" and price and amount:
        side_ru = "Покупка" if side == "buy" else "Продажа" if side == "sell" else "Ордер"
        title = f"{side_ru} {amount}{pair_label} @ {price}"
    elif event_type == "filled" and price:
        side_ru = "Куплено" if side == "buy" else "Продано" if side == "sell" else "Исполнено"
        pnl_part = f", PnL: {pnl_delta}" if pnl_delta else ""
        title = f"{side_ru} @ {price}{pnl_part}"
        if pnl_delta and Decimal(str(pnl_delta)) > 0:
            severity = "success"
            emoji = "💰"
    elif event_type == "cancelled":
        title = f"Отменён ордер @ {price}" if price else "Ордер отменён"
    elif event_type == "flipped" and price:
        title = f"Переворот @ {price}"
    elif event_type == "grid_rebuilt":
        reason = (payload or {}).get("reason", "")
        title = f"Сетка перестроена{f': {reason}' if reason else ''}"
    elif event_type == "adaptive_shift":
        direction = (payload or {}).get("direction", "")
        title = f"Сдвиг подсетки {direction}" if direction else "Сдвиг адаптивной подсетки"
    else:
        title = base_title

    body = f"{grid_label}{pair_label}".strip() if grid_label or pair_label else None

    return TranslatedMessage(severity=severity, title=title, body=body, emoji=emoji)


# ---------------------------------------------------------------------------
# Bot Log translations (ошибки, системные события)
# ---------------------------------------------------------------------------

_BOT_LOG_PATTERNS: list[tuple[str, str, str, str]] = [
    # (substring_match, severity, emoji, translated_title)
    ("Сетка запущена",        "success",  "🟢", ""),  # pass-through
    ("Сетка остановлена",     "info",     "🔴", ""),
    ("Новые сделки",          "success",  "💹", ""),
    ("Воркер запущен",        "info",     "⚙️", "Воркер запущен"),
    ("Воркер остановлен",     "warning",  "⚙️", "Воркер остановлен"),
    ("Команда получена",      "info",     "📨", ""),
    ("Команда: остановить",   "warning",  "⏹️", "Остановка всех сеток"),
]


def translate_bot_log(
    message: str,
    *,
    level: str = "info",
    source: str | None = None,
    traceback_text: str | None = None,
) -> TranslatedMessage:
    """Перевести BotLog запись в человекочитаемое сообщение."""
    # Проверяем известные паттерны
    for pattern, severity, emoji, title in _BOT_LOG_PATTERNS:
        if pattern in message:
            return TranslatedMessage(
                severity=severity,
                title=title or message,
                body=f"Источник: {source}" if source else None,
                emoji=emoji,
            )

    # Если ошибка — диагностируем
    if level in ("error", "critical"):
        diagnosis = diagnose_error(message, traceback=traceback_text, source=source)
        return diagnosis

    # Дефолт — pass-through
    level_emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🔥"}
    return TranslatedMessage(
        severity=level,
        title=message,
        body=f"Источник: {source}" if source else None,
        emoji=level_emoji.get(level, "ℹ️"),
    )


# ---------------------------------------------------------------------------
# ErrorDiagnostor — автоматическая диагностика ошибок
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ErrorDiagnosis(TranslatedMessage):
    """Расширенный результат с диагнозом и рекомендацией."""

    cause: str | None = None        # предполагаемая причина
    fix: str | None = None          # рекомендация по исправлению
    doc_ref: str | None = None      # ссылка на документацию


# (pattern_in_message_or_traceback, cause, fix, doc_ref)
_ERROR_CATALOG: list[tuple[str, str, str, str, str | None]] = [
    # ── ccxt / биржа ──
    (
        "insufficient_funds",
        "Недостаточно средств",
        "На счёте биржи не хватает средств для размещения ордера.",
        "Проверьте баланс на бирже. Убедитесь что деньги на Spot-кошельке, а не на Funding.",
        "Ошибки биржи#insufficient_funds",
    ),
    (
        "InsufficientFunds",
        "Недостаточно средств",
        "Биржа отклонила ордер: не хватает баланса.",
        "Переведите средства на Spot-кошелёк или уменьшите lot_size.",
        "Ошибки биржи#insufficient_funds",
    ),
    (
        "InvalidOrder",
        "Некорректный ордер",
        "Параметры ордера не прошли валидацию биржи (цена, количество, минимум).",
        "Проверьте lot_size (мин. ~$5 для BTC), шаг цены и допустимые пределы.",
        "Ошибки биржи#invalid_order",
    ),
    (
        "minimum order",
        "Слишком маленький ордер",
        "Размер ордера меньше минимального для этой пары.",
        "Увеличьте lot_size. Для BTC/USDT на Bybit минимум ~$5.",
        "Ошибки биржи#minimum_order",
    ),
    (
        "AuthenticationError",
        "Ошибка аутентификации API",
        "Биржа отклонила API-ключ или подпись.",
        "Проверьте API-ключ и секрет. Убедитесь что IP сервера в whitelist.",
        "Ошибки биржи#auth_error",
    ),
    (
        "ExchangeNotAvailable",
        "Биржа недоступна",
        "Сервер биржи временно недоступен или на обслуживании.",
        "Бот автоматически повторит запрос. Если проблема сохраняется — проверьте статус биржи.",
        "Ошибки биржи#exchange_unavailable",
    ),
    (
        "RateLimitExceeded",
        "Превышен лимит запросов",
        "Слишком много запросов к API биржи.",
        "Бот автоматически замедлится. Если частые — увеличьте rebuild_timeout_sec.",
        "Ошибки биржи#rate_limit",
    ),
    (
        "NetworkError",
        "Сетевая ошибка",
        "Проблема сетевого подключения к бирже.",
        "Проверьте интернет-соединение на сервере. Бот повторит автоматически.",
        "Ошибки биржи#network_error",
    ),
    (
        "RequestTimeout",
        "Таймаут запроса",
        "Биржа не ответила вовремя.",
        "Обычно временная проблема. Бот повторит автоматически.",
        "Ошибки биржи#timeout",
    ),

    # ── Bybit specific codes ──
    (
        "retCode\":10001",
        "Bybit: ошибка параметров",
        "Некорректные параметры запроса к Bybit API.",
        "Проверьте настройки сетки: символ, lot_size, шаг цены.",
        "Ошибки биржи#bybit_10001",
    ),
    (
        "retCode\":10003",
        "Bybit: невалидный API-ключ",
        "API-ключ не распознан биржей Bybit.",
        "Пересоздайте API-ключ в Bybit. Убедитесь что тип System-generated, разрешения Spot.",
        "Ошибки биржи#bybit_10003",
    ),
    (
        "retCode\":110007",
        "Bybit: недостаточный баланс",
        "На Bybit Spot-кошельке недостаточно средств.",
        "Переведите USDT из Funding в Spot через Transfer на бирже.",
        "Ошибки биржи#bybit_110007",
    ),
    (
        "retCode\":110012",
        "Bybit: недостаточный доступный баланс",
        "Доступный баланс заблокирован другими ордерами.",
        "Отмените лишние ордера или пополните Spot-кошелёк.",
        "Ошибки биржи#bybit_110012",
    ),

    # ── Binance specific ──
    (
        "code\":-2015",
        "Binance: невалидный API-ключ",
        "Binance не распознал API-ключ.",
        "Проверьте API-ключ и IP whitelist в настройках Binance.",
        "Ошибки биржи#binance_2015",
    ),
    (
        "code\":-2010",
        "Binance: ордер отклонён",
        "Binance отклонил создание ордера.",
        "Проверьте баланс и параметры ордера (минимальный размер, шаг цены).",
        "Ошибки биржи#binance_2010",
    ),

    # ── Внутренние ошибки ──
    (
        "ConnectionRefusedError",
        "Отказ соединения",
        "Не удалось подключиться к сервису (Redis, PostgreSQL или биржа).",
        "Проверьте что все контейнеры запущены: docker compose ps",
        "Системные ошибки#connection_refused",
    ),
    (
        "OperationalError",
        "Ошибка базы данных",
        "PostgreSQL вернул ошибку при выполнении запроса.",
        "Проверьте подключение к БД и наличие миграций: alembic upgrade head",
        "Системные ошибки#db_error",
    ),
    (
        "Redis",
        "Ошибка Redis",
        "Не удалось выполнить операцию с Redis.",
        "Проверьте что Redis запущен: docker compose ps redis",
        "Системные ошибки#redis_error",
    ),
    (
        "JWT",
        "Ошибка аутентификации",
        "Невалидный или истёкший JWT токен.",
        "Перелогиньтесь в систему. Проверьте JWT_SECRET в .env.",
        "Системные ошибки#jwt_error",
    ),
    (
        "ValidationError",
        "Ошибка валидации",
        "Данные не прошли валидацию (Pydantic или настройки).",
        "Проверьте все обязательные поля в .env и параметры запроса.",
        "Системные ошибки#validation_error",
    ),
]


def diagnose_error(
    message: str,
    *,
    traceback: str | None = None,
    source: str | None = None,
) -> ErrorDiagnosis:
    """Диагностировать ошибку по сообщению и traceback."""
    search_text = f"{message}\n{traceback or ''}"

    for pattern, title, cause, fix, doc_ref in _ERROR_CATALOG:
        if pattern in search_text:
            return ErrorDiagnosis(
                severity="error",
                title=title,
                body=f"Источник: {source}" if source else None,
                emoji="❌",
                cause=cause,
                fix=fix,
                doc_ref=doc_ref,
            )

    # Неизвестная ошибка
    return ErrorDiagnosis(
        severity="error",
        title="Неизвестная ошибка",
        body=f"{message[:200]}\nИсточник: {source}" if source else message[:200],
        emoji="❓",
        cause="Ошибка не найдена в каталоге известных проблем.",
        fix="Проверьте traceback в логах. Если проблема повторяется — сообщите разработчику.",
        doc_ref=None,
    )


# ---------------------------------------------------------------------------
# Утилиты для интеграции
# ---------------------------------------------------------------------------

def format_for_telegram(msg: TranslatedMessage) -> str:
    """Форматировать сообщение для Telegram (Markdown)."""
    lines = [f"{msg.emoji} *{msg.title}*"]
    if msg.body:
        lines.append(msg.body)
    if isinstance(msg, ErrorDiagnosis):
        if msg.cause:
            lines.append(f"🔍 Причина: {msg.cause}")
        if msg.fix:
            lines.append(f"💡 Решение: {msg.fix}")
    return "\n".join(lines)


def format_for_frontend(msg: TranslatedMessage) -> dict:
    """Сериализовать для JSON-ответа на фронтенд."""
    result = {
        "severity": msg.severity,
        "title": msg.title,
        "body": msg.body,
        "emoji": msg.emoji,
    }
    if isinstance(msg, ErrorDiagnosis):
        result["cause"] = msg.cause
        result["fix"] = msg.fix
        result["doc_ref"] = msg.doc_ref
    return result
