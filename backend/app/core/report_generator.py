"""Генератор отчётов с графиками и текстовой аналитикой по activity logs сетки."""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from decimal import Decimal

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
from matplotlib.gridspec import GridSpec


# ---------------------------------------------------------------------------
# Текстовый отчёт
# ---------------------------------------------------------------------------

def generate_text_report(
    grid_name: str,
    symbol: str,
    logs: list[dict],
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> str:
    """Генерирует подробный текстовый отчёт на русском языке."""

    ticks = [l for l in logs if l["event"] == "tick"]
    fills = [l for l in logs if l["event"] == "fill"]
    rebuilds = [l for l in logs if l["event"] == "rebuild"]
    shifts = [l for l in logs if l["event"] == "shift"]
    errors = [l for l in logs if l["event"] == "error"]
    starts = [l for l in logs if l["event"] == "start"]
    stops = [l for l in logs if l["event"] == "stop"]

    pnl_values = [float(l["data"].get("realized_pnl", 0)) for l in ticks]
    spread_values = [float(l["data"].get("spread", 0)) for l in ticks]
    tick_ms_values = [float(l["data"].get("tick_ms", 0)) for l in ticks]
    api_per_sec = [float(l["data"].get("api_req_per_sec", 0)) for l in ticks]
    api_per_hour = [float(l["data"].get("api_req_per_hour", 0)) for l in ticks]
    bid_values = [float(l["data"].get("bid", 0)) for l in ticks]
    placed_values = [int(l["data"].get("placed_orders", 0)) for l in ticks]

    lines: list[str] = []
    sep = "=" * 60

    # --- Заголовок ---
    lines.append(sep)
    lines.append(f"  ОТЧЁТ ПО СЕТКЕ: {grid_name} ({symbol})")
    lines.append(sep)
    if period_start and period_end:
        duration = period_end - period_start
        hours = duration.total_seconds() / 3600
        lines.append(f"  Период: {period_start.strftime('%Y-%m-%d %H:%M')} — {period_end.strftime('%Y-%m-%d %H:%M')} ({hours:.1f} ч)")
    lines.append(f"  Всего записей: {len(logs)}")
    lines.append("")

    # --- 1. Общая сводка ---
    lines.append("─" * 60)
    lines.append("  1. ОБЩАЯ СВОДКА")
    lines.append("─" * 60)
    lines.append(f"  Тиков обработано:      {len(ticks)}")
    lines.append(f"  Сделок (fill):         {len(fills)}")
    lines.append(f"  Перестроений (rebuild): {len(rebuilds)}")
    lines.append(f"  Сдвигов (shift):       {len(shifts)}")
    lines.append(f"  Ошибок:                {len(errors)}")
    lines.append(f"  Запусков:              {len(starts)}")
    lines.append(f"  Остановок:             {len(stops)}")
    lines.append("")

    # --- 2. Прибыль (PnL) ---
    lines.append("─" * 60)
    lines.append("  2. ПРИБЫЛЬ (PnL)")
    lines.append("─" * 60)
    if pnl_values:
        start_pnl = pnl_values[0]
        end_pnl = pnl_values[-1]
        delta_pnl = end_pnl - start_pnl
        max_pnl = max(pnl_values)
        min_pnl = min(pnl_values)

        lines.append(f"  PnL на начало периода: {start_pnl:.8f} USDT")
        lines.append(f"  PnL на конец периода:  {end_pnl:.8f} USDT")
        lines.append(f"  Изменение за период:   {delta_pnl:+.8f} USDT")
        lines.append(f"  Максимум за период:    {max_pnl:.8f} USDT")
        lines.append(f"  Минимум за период:     {min_pnl:.8f} USDT")
        lines.append("")

        if delta_pnl > 0:
            lines.append("  → Сетка принесла прибыль за данный период.")
        elif delta_pnl == 0:
            lines.append("  → Прибыль не изменилась — сделок в периоде не было.")
        else:
            lines.append("  → Внимание: PnL снизился. Возможны убыточные сделки или перестроения.")
    else:
        lines.append("  Нет данных о PnL.")
    lines.append("")

    # --- 3. Цена и рынок ---
    lines.append("─" * 60)
    lines.append("  3. ЦЕНА И РЫНОК")
    lines.append("─" * 60)
    if bid_values:
        start_price = bid_values[0]
        end_price = bid_values[-1]
        max_price = max(bid_values)
        min_price = min(bid_values)
        price_change = end_price - start_price
        price_change_pct = (price_change / start_price * 100) if start_price else 0

        lines.append(f"  Цена на начало:   {start_price:.2f} USDT")
        lines.append(f"  Цена на конец:    {end_price:.2f} USDT")
        lines.append(f"  Изменение:        {price_change:+.2f} ({price_change_pct:+.2f}%)")
        lines.append(f"  Максимум:         {max_price:.2f} USDT")
        lines.append(f"  Минимум:          {min_price:.2f} USDT")
        lines.append(f"  Диапазон:         {max_price - min_price:.2f} USDT")
        lines.append("")

        if abs(price_change_pct) < 0.5:
            lines.append("  → Рынок был в боковике — идеальные условия для grid-бота.")
        elif price_change_pct > 2:
            lines.append("  → Заметный рост цены. Сетка могла оказаться ниже рынка.")
        elif price_change_pct < -2:
            lines.append("  → Заметное падение цены. Сетка могла оказаться выше рынка.")
        else:
            lines.append("  → Умеренное движение цены, нормальные условия для работы сетки.")
    else:
        lines.append("  Нет данных о ценах.")
    lines.append("")

    # --- 4. Спред ---
    lines.append("─" * 60)
    lines.append("  4. СПРЕД (BID-ASK)")
    lines.append("─" * 60)
    if spread_values:
        avg_spread = sum(spread_values) / len(spread_values)
        max_spread = max(spread_values)
        min_spread = min(spread_values)

        lines.append(f"  Средний спред:    {avg_spread:.4f} USDT")
        lines.append(f"  Максимальный:     {max_spread:.4f} USDT")
        lines.append(f"  Минимальный:      {min_spread:.4f} USDT")
        lines.append("")
        lines.append("  Спред — это разница между ценой покупки (bid) и продажи (ask).")
        lines.append("  Чем меньше спред, тем лучше ликвидность и ниже издержки.")

        if avg_spread < 0.5:
            lines.append("  → Спред очень узкий — отличная ликвидность.")
        elif avg_spread < 2:
            lines.append("  → Спред в норме.")
        else:
            lines.append("  → Спред широкий — возможны проблемы с ликвидностью.")
    lines.append("")

    # --- 5. Сделки ---
    lines.append("─" * 60)
    lines.append("  5. СДЕЛКИ (FILLS)")
    lines.append("─" * 60)
    if fills:
        total_profit = sum(float(f["data"].get("profit", 0)) for f in fills)
        profitable = sum(1 for f in fills if float(f["data"].get("profit", 0)) > 0)
        unprofitable = len(fills) - profitable

        lines.append(f"  Всего сделок:         {len(fills)}")
        lines.append(f"  Прибыльных:           {profitable}")
        lines.append(f"  Убыточных/нулевых:    {unprofitable}")
        lines.append(f"  Суммарный профит:     {total_profit:.8f} USDT")
        if fills:
            lines.append(f"  Средний профит:       {total_profit / len(fills):.8f} USDT")
        lines.append("")

        lines.append("  Последние 5 сделок:")
        for f in fills[-5:]:
            t = f["created_at"]
            ts = t.strftime("%H:%M:%S") if isinstance(t, datetime) else str(t)
            side = f["data"].get("side", "?")
            price = f["data"].get("price", "?")
            profit = f["data"].get("profit", "0")
            lines.append(f"    {ts}  {side:>5}  цена: {price}  профит: {profit}")
    else:
        lines.append("  Сделок за период не было.")
        lines.append("  Это нормально при боковом рынке — ордера ждут исполнения.")
    lines.append("")

    # --- 6. Перестроения и сдвиги ---
    lines.append("─" * 60)
    lines.append("  6. ПЕРЕСТРОЕНИЯ И СДВИГИ СЕТКИ")
    lines.append("─" * 60)
    if rebuilds:
        lines.append(f"  Перестроений: {len(rebuilds)}")
        lines.append("  Перестроение (rebuild) — полная пересборка сетки ордеров вокруг")
        lines.append("  новой цены. Происходит когда цена выходит за границы сетки")
        lines.append("  и не возвращается в течение таймаута.")
        lines.append("")
        for r in rebuilds[-3:]:
            t = r["created_at"]
            ts = t.strftime("%H:%M:%S") if isinstance(t, datetime) else str(t)
            d = r["data"]
            lines.append(f"    {ts}  центр: {d.get('old_center', '?')} → {d.get('new_center', '?')}")
            lines.append(f"             отменено: {d.get('cancelled_orders', '?')}, создано: {d.get('new_orders', '?')}")
    else:
        lines.append("  Перестроений не было — сетка работала стабильно в своём диапазоне.")
    lines.append("")

    if shifts:
        lines.append(f"  Сдвигов: {len(shifts)}")
        lines.append("  Сдвиг (shift) — плавное смещение ордеров адаптивной сетки")
        lines.append("  вслед за ценой без полной пересборки.")
        lines.append("")
        for s in shifts[-3:]:
            t = s["created_at"]
            ts = t.strftime("%H:%M:%S") if isinstance(t, datetime) else str(t)
            d = s["data"]
            direction = "вверх ↑" if d.get("direction") == "up" else "вниз ↓"
            lines.append(f"    {ts}  {direction}  дельта: {d.get('delta', '?')}  цена: {d.get('current_price', '?')}")
    elif not rebuilds:
        lines.append("  Сдвигов не было.")
    lines.append("")

    # --- 7. Производительность ---
    lines.append("─" * 60)
    lines.append("  7. ПРОИЗВОДИТЕЛЬНОСТЬ")
    lines.append("─" * 60)
    if tick_ms_values:
        avg_ms = sum(tick_ms_values) / len(tick_ms_values)
        max_ms = max(tick_ms_values)
        min_ms = min(tick_ms_values)
        slow_ticks = sum(1 for t in tick_ms_values if t > 10000)

        lines.append(f"  Средняя длительность тика:  {avg_ms:.0f} мс ({avg_ms/1000:.1f} сек)")
        lines.append(f"  Максимальная:               {max_ms:.0f} мс ({max_ms/1000:.1f} сек)")
        lines.append(f"  Минимальная:                {min_ms:.0f} мс ({min_ms/1000:.1f} сек)")
        lines.append(f"  Медленных тиков (>10 сек):  {slow_ticks}")
        lines.append("")
        lines.append("  Тик — один цикл работы бота: проверка цены, проверка ордеров,")
        lines.append("  размещение новых ордеров. Включает сетевые запросы к бирже.")

        if avg_ms < 3000:
            lines.append("  → Отличная скорость, бот реагирует быстро.")
        elif avg_ms < 6000:
            lines.append("  → Нормальная скорость. Задержки связаны с сетью/прокси.")
        else:
            lines.append("  → Тики медленные. Возможно проблемы с прокси или перегрузка API.")

        if slow_ticks > 0:
            pct = slow_ticks / len(tick_ms_values) * 100
            lines.append(f"  → {slow_ticks} тиков ({pct:.1f}%) были дольше 10 секунд.")
    lines.append("")

    # --- 8. Нагрузка на API ---
    lines.append("─" * 60)
    lines.append("  8. НАГРУЗКА НА API БИРЖИ")
    lines.append("─" * 60)
    if api_per_sec and api_per_hour:
        avg_rps = sum(api_per_sec) / len(api_per_sec)
        max_rps = max(api_per_sec)
        avg_rph = sum(api_per_hour) / len(api_per_hour)
        max_rph = max(api_per_hour)

        lines.append(f"  Средняя частота:   {avg_rps:.2f} запросов/сек")
        lines.append(f"  Максимальная:      {max_rps:.2f} запросов/сек")
        lines.append(f"  Средняя за час:    {avg_rph:.0f} запросов/час")
        lines.append(f"  Максимум за час:   {max_rph:.0f} запросов/час")
        lines.append("")
        lines.append("  Каждый тик делает несколько запросов к API биржи:")
        lines.append("  fetch_ticker, fetch_open_orders, fetch_order_status и др.")
        lines.append("  Лимиты Binance: ~1200 req/min, Bybit: ~120 req/min.")

        if max_rph > 50000:
            lines.append("  → ВНИМАНИЕ: высокая нагрузка, риск блокировки по rate limit.")
        elif max_rph > 20000:
            lines.append("  → Нагрузка повышенная, но в пределах лимитов.")
        else:
            lines.append("  → Нагрузка в норме, далеко от лимитов биржи.")
    lines.append("")

    # --- 9. Активные ордера ---
    lines.append("─" * 60)
    lines.append("  9. ОРДЕРА")
    lines.append("─" * 60)
    if placed_values:
        avg_placed = sum(placed_values) / len(placed_values)
        lines.append(f"  Среднее кол-во ордеров: {avg_placed:.0f}")
        lines.append(f"  Максимум:               {max(placed_values)}")
        lines.append(f"  Минимум:                {min(placed_values)}")
        lines.append("")
        lines.append("  Количество активных ордеров на бирже в каждый момент времени.")
        lines.append("  Определяется параметрами levels_above + levels_below сетки.")
    lines.append("")

    # --- 10. Ошибки ---
    if errors:
        lines.append("─" * 60)
        lines.append("  10. ОШИБКИ")
        lines.append("─" * 60)
        lines.append(f"  Всего ошибок: {len(errors)}")
        lines.append("")
        for e in errors[-5:]:
            t = e["created_at"]
            ts = t.strftime("%H:%M:%S") if isinstance(t, datetime) else str(t)
            lines.append(f"    {ts}  [{e['data'].get('context', '?')}] {e['data'].get('error', '?')[:100]}")
        lines.append("")

    # --- Заключение ---
    lines.append(sep)
    lines.append("  ЗАКЛЮЧЕНИЕ")
    lines.append(sep)

    conclusions: list[str] = []
    if pnl_values:
        delta_pnl = pnl_values[-1] - pnl_values[0]
        if delta_pnl > 0:
            conclusions.append(f"Прибыль выросла на {delta_pnl:.8f} USDT.")
        elif delta_pnl == 0:
            conclusions.append("Прибыль не изменилась — ожидание сделок.")

    if not rebuilds and not shifts:
        conclusions.append("Сетка работала стабильно без перестроений.")
    elif rebuilds:
        conclusions.append(f"Было {len(rebuilds)} перестроений — цена выходила за границы.")

    if errors:
        conclusions.append(f"Зафиксировано {len(errors)} ошибок — требует внимания.")
    else:
        conclusions.append("Ошибок не было.")

    if tick_ms_values:
        avg_ms = sum(tick_ms_values) / len(tick_ms_values)
        if avg_ms > 6000:
            conclusions.append("Тики медленные — рекомендуется проверить прокси/сеть.")
        else:
            conclusions.append("Производительность в норме.")

    for i, c in enumerate(conclusions, 1):
        lines.append(f"  {i}. {c}")

    lines.append("")
    lines.append(sep)
    lines.append(f"  Отчёт сгенерирован: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append(sep)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Графический отчёт (PNG)
# ---------------------------------------------------------------------------

def generate_grid_report(
    grid_name: str,
    symbol: str,
    logs: list[dict],
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> bytes:
    """Генерирует PNG-отчёт с графиками из activity logs.

    Returns:
        PNG-изображение в байтах
    """
    # Разделяем логи по типам
    ticks = [l for l in logs if l["event"] == "tick"]
    fills = [l for l in logs if l["event"] == "fill"]
    rebuilds = [l for l in logs if l["event"] == "rebuild"]
    shifts = [l for l in logs if l["event"] == "shift"]
    api_stats = [l for l in logs if l["event"] in ("tick", "api_stats")]

    # Извлекаем данные для графиков
    tick_times = [l["created_at"] for l in ticks]
    pnl_values = [float(l["data"].get("realized_pnl", 0)) for l in ticks]
    spread_values = [float(l["data"].get("spread", 0)) for l in ticks]
    tick_ms_values = [float(l["data"].get("tick_ms", 0)) for l in ticks]
    api_per_sec = [float(l["data"].get("api_req_per_sec", 0)) for l in api_stats]
    api_per_hour = [float(l["data"].get("api_req_per_hour", 0)) for l in api_stats]
    api_times = [l["created_at"] for l in api_stats]
    bid_values = [float(l["data"].get("bid", 0)) for l in ticks]
    ask_values = [float(l["data"].get("ask", 0)) for l in ticks]

    fill_times = [l["created_at"] for l in fills]
    fill_profits = [float(l["data"].get("profit", 0)) for l in fills]

    # --- Подготовка текстовой аналитики для вставки в изображение ---
    text_blocks: list[str] = []

    if pnl_values:
        delta = pnl_values[-1] - pnl_values[0]
        sign = "+" if delta >= 0 else ""
        text_blocks.append(
            f"PnL: {pnl_values[-1]:.8f} USDT (за период {sign}{delta:.8f})"
        )

    if bid_values:
        price_change = bid_values[-1] - bid_values[0]
        pct = price_change / bid_values[0] * 100 if bid_values[0] else 0
        text_blocks.append(
            f"Цена: {bid_values[0]:.2f} → {bid_values[-1]:.2f} ({pct:+.2f}%)"
        )

    if spread_values:
        text_blocks.append(f"Средний спред: {sum(spread_values)/len(spread_values):.4f}")

    text_blocks.append(f"Тиков: {len(ticks)}  |  Сделок: {len(fills)}  |  Перестроений: {len(rebuilds)}  |  Сдвигов: {len(shifts)}")

    if tick_ms_values:
        avg_ms = sum(tick_ms_values) / len(tick_ms_values)
        text_blocks.append(f"Средний тик: {avg_ms:.0f} мс  |  Макс: {max(tick_ms_values):.0f} мс")

    if api_per_hour:
        text_blocks.append(
            f"API: ~{sum(api_per_sec)/len(api_per_sec):.1f} req/s  |  ~{sum(api_per_hour)/len(api_per_hour):.0f} req/h"
        )

    # --- Построение графиков ---
    n_charts = 5
    # Дополнительное место сверху для текстового блока
    fig = plt.figure(figsize=(14, 4 * n_charts + 3), dpi=100)
    fig.patch.set_facecolor("#1a1a2e")

    plt.style.use("dark_background")
    title_color = "#e0e0e0"
    grid_color = "#333355"
    accent_green = "#00d4aa"
    accent_red = "#ff4757"
    accent_blue = "#4dabf7"
    accent_orange = "#ffa94d"
    accent_purple = "#b197fc"

    # GridSpec: текстовый блок сверху + 5 графиков
    gs = GridSpec(n_charts + 1, 1, figure=fig, height_ratios=[1.2] + [1] * n_charts, hspace=0.4)

    # --- Текстовый блок сверху ---
    ax_text = fig.add_subplot(gs[0])
    ax_text.set_facecolor("#16213e")
    ax_text.set_xlim(0, 1)
    ax_text.set_ylim(0, 1)
    ax_text.axis("off")

    period_str = ""
    if period_start and period_end:
        period_str = f"{period_start.strftime('%Y-%m-%d %H:%M')} — {period_end.strftime('%Y-%m-%d %H:%M')}"

    header = f"Отчёт: {grid_name} ({symbol})"
    if period_str:
        header += f"\n{period_str}"

    ax_text.text(
        0.5, 0.92, header,
        transform=ax_text.transAxes, fontsize=15, color=title_color,
        fontweight="bold", ha="center", va="top",
    )

    summary_text = "\n".join(text_blocks)
    ax_text.text(
        0.5, 0.55, summary_text,
        transform=ax_text.transAxes, fontsize=11, color="#cccccc",
        ha="center", va="center", family="monospace",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#0f3460", edgecolor="#333355", alpha=0.8),
    )

    # Заключение
    conclusions = []
    if pnl_values:
        delta = pnl_values[-1] - pnl_values[0]
        if delta > 0:
            conclusions.append("✓ Прибыль росла")
        elif delta == 0:
            conclusions.append("— Прибыль без изменений")
    if not rebuilds and not shifts:
        conclusions.append("✓ Сетка стабильна")
    elif rebuilds:
        conclusions.append(f"! {len(rebuilds)} перестроений")
    if tick_ms_values and sum(tick_ms_values)/len(tick_ms_values) > 6000:
        conclusions.append("! Медленные тики")

    if conclusions:
        ax_text.text(
            0.5, 0.08, "   ".join(conclusions),
            transform=ax_text.transAxes, fontsize=10, color=accent_green,
            ha="center", va="bottom",
        )

    axes = [fig.add_subplot(gs[i + 1]) for i in range(n_charts)]

    # --- 1. PnL ---
    ax = axes[0]
    ax.set_facecolor("#1a1a2e")
    if tick_times and pnl_values:
        ax.fill_between(tick_times, pnl_values, alpha=0.3, color=accent_green)
        ax.plot(tick_times, pnl_values, color=accent_green, linewidth=1.5, label="Реализованный PnL")
        ax.set_ylabel("PnL (USDT)", color=title_color)
        ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Реализованная прибыль", color=title_color, fontsize=12)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    for r in rebuilds:
        ax.axvline(r["created_at"], color=accent_orange, alpha=0.5, linestyle="--", linewidth=0.8)
    for s in shifts:
        ax.axvline(s["created_at"], color=accent_purple, alpha=0.5, linestyle=":", linewidth=0.8)

    # --- 2. Price + Fills ---
    ax = axes[1]
    ax.set_facecolor("#1a1a2e")
    if tick_times and bid_values:
        ax.plot(tick_times, bid_values, color=accent_blue, linewidth=1, alpha=0.7, label="Bid (покупка)")
        ax.plot(tick_times, ask_values, color=accent_orange, linewidth=1, alpha=0.7, label="Ask (продажа)")
    if fill_times:
        colors = [accent_green if p >= 0 else accent_red for p in fill_profits]
        ax.scatter(fill_times, [float(f["data"].get("price", 0)) for f in fills],
                   c=colors, s=30, zorder=5, label="Сделки")
    ax.set_title("Цена и сделки", color=title_color, fontsize=12)
    ax.set_ylabel("Цена (USDT)", color=title_color)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    # --- 3. Spread ---
    ax = axes[2]
    ax.set_facecolor("#1a1a2e")
    if tick_times and spread_values:
        ax.fill_between(tick_times, spread_values, alpha=0.3, color=accent_purple)
        ax.plot(tick_times, spread_values, color=accent_purple, linewidth=1, label="Спред")
        ax.set_ylabel("Спред (USDT)", color=title_color)
        ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Спред (разница Bid-Ask)", color=title_color, fontsize=12)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    # --- 4. Tick Duration ---
    ax = axes[3]
    ax.set_facecolor("#1a1a2e")
    if tick_times and tick_ms_values:
        ax.bar(tick_times, tick_ms_values, width=0.0005, color=accent_blue, alpha=0.7)
        avg_ms = sum(tick_ms_values) / len(tick_ms_values)
        ax.axhline(avg_ms, color=accent_red, linestyle="--", linewidth=1, label=f"Среднее: {avg_ms:.0f} мс")
        ax.set_ylabel("мс", color=title_color)
        ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Длительность тика (скорость реакции бота)", color=title_color, fontsize=12)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    # --- 5. API Rate ---
    ax = axes[4]
    ax.set_facecolor("#1a1a2e")
    if api_times and api_per_sec:
        ax2 = ax.twinx()
        ax.plot(api_times, api_per_sec, color=accent_green, linewidth=1.5, label="запросов/сек")
        ax2.plot(api_times, api_per_hour, color=accent_orange, linewidth=1.5, label="запросов/час")
        ax.set_ylabel("запросов/сек", color=accent_green)
        ax2.set_ylabel("запросов/час", color=accent_orange)
        ax.legend(loc="upper left", fontsize=9)
        ax2.legend(loc="upper right", fontsize=9)
        ax2.tick_params(colors=title_color)
    ax.set_title("Нагрузка на API биржи", color=title_color, fontsize=12)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    # Форматирование дат на оси X
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        for spine in ax.spines.values():
            spine.set_color(grid_color)

    # Экспорт в PNG
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
