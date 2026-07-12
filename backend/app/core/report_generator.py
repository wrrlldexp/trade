"""Генератор отчётов с графиками по activity logs сетки."""

from __future__ import annotations

import io
from datetime import datetime
from decimal import Decimal

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure


def generate_grid_report(
    grid_name: str,
    symbol: str,
    logs: list[dict],
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> bytes:
    """Генерирует PNG-отчёт с графиками из activity logs.

    Args:
        grid_name: Имя сетки
        symbol: Торговая пара
        logs: Список записей из grid_activity_logs (event, data, created_at)
        period_start/end: Границы периода для заголовка

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

    # Определяем кол-во графиков
    n_charts = 5  # PnL, Price+Fills, Spread, Tick Duration, API Rate
    fig, axes = plt.subplots(n_charts, 1, figsize=(14, 4 * n_charts), dpi=100)
    fig.patch.set_facecolor("#1a1a2e")

    # Стиль
    plt.style.use("dark_background")
    title_color = "#e0e0e0"
    grid_color = "#333355"
    accent_green = "#00d4aa"
    accent_red = "#ff4757"
    accent_blue = "#4dabf7"
    accent_orange = "#ffa94d"
    accent_purple = "#b197fc"

    # Заголовок отчёта
    period_str = ""
    if period_start and period_end:
        period_str = f" | {period_start.strftime('%Y-%m-%d %H:%M')} — {period_end.strftime('%Y-%m-%d %H:%M')}"
    fig.suptitle(
        f"Grid Report: {grid_name} ({symbol}){period_str}",
        fontsize=16,
        color=title_color,
        fontweight="bold",
        y=0.995,
    )

    # --- 1. PnL ---
    ax = axes[0]
    ax.set_facecolor("#1a1a2e")
    if tick_times and pnl_values:
        ax.fill_between(tick_times, pnl_values, alpha=0.3, color=accent_green)
        ax.plot(tick_times, pnl_values, color=accent_green, linewidth=1.5, label="Realized PnL")
        ax.set_ylabel("PnL (USDT)", color=title_color)
        ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Realized PnL", color=title_color, fontsize=12)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    # Отметки rebuild/shift
    for r in rebuilds:
        ax.axvline(r["created_at"], color=accent_orange, alpha=0.5, linestyle="--", linewidth=0.8)
    for s in shifts:
        ax.axvline(s["created_at"], color=accent_purple, alpha=0.5, linestyle=":", linewidth=0.8)

    # --- 2. Price + Fills ---
    ax = axes[1]
    ax.set_facecolor("#1a1a2e")
    if tick_times and bid_values:
        ax.plot(tick_times, bid_values, color=accent_blue, linewidth=1, alpha=0.7, label="Bid")
        ax.plot(tick_times, ask_values, color=accent_orange, linewidth=1, alpha=0.7, label="Ask")
    if fill_times:
        colors = [accent_green if p >= 0 else accent_red for p in fill_profits]
        ax.scatter(fill_times, [float(f["data"].get("price", 0)) for f in fills],
                   c=colors, s=30, zorder=5, label="Fills")
    ax.set_title("Price & Fills", color=title_color, fontsize=12)
    ax.set_ylabel("Price", color=title_color)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    # --- 3. Spread ---
    ax = axes[2]
    ax.set_facecolor("#1a1a2e")
    if tick_times and spread_values:
        ax.fill_between(tick_times, spread_values, alpha=0.3, color=accent_purple)
        ax.plot(tick_times, spread_values, color=accent_purple, linewidth=1, label="Spread")
        ax.set_ylabel("Spread", color=title_color)
        ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Bid-Ask Spread", color=title_color, fontsize=12)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    # --- 4. Tick Duration ---
    ax = axes[3]
    ax.set_facecolor("#1a1a2e")
    if tick_times and tick_ms_values:
        ax.bar(tick_times, tick_ms_values, width=0.0005, color=accent_blue, alpha=0.7)
        avg_ms = sum(tick_ms_values) / len(tick_ms_values)
        ax.axhline(avg_ms, color=accent_red, linestyle="--", linewidth=1, label=f"Avg: {avg_ms:.0f}ms")
        ax.set_ylabel("ms", color=title_color)
        ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Tick Duration", color=title_color, fontsize=12)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    # --- 5. API Rate ---
    ax = axes[4]
    ax.set_facecolor("#1a1a2e")
    if api_times and api_per_sec:
        ax2 = ax.twinx()
        ax.plot(api_times, api_per_sec, color=accent_green, linewidth=1.5, label="req/s")
        ax2.plot(api_times, api_per_hour, color=accent_orange, linewidth=1.5, label="req/h")
        ax.set_ylabel("req/s", color=accent_green)
        ax2.set_ylabel("req/h", color=accent_orange)
        ax.legend(loc="upper left", fontsize=9)
        ax2.legend(loc="upper right", fontsize=9)
        ax2.tick_params(colors=title_color)
    ax.set_title("API Call Rate", color=title_color, fontsize=12)
    ax.grid(True, alpha=0.2, color=grid_color)
    ax.tick_params(colors=title_color)

    # Форматирование дат на оси X
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        for spine in ax.spines.values():
            spine.set_color(grid_color)

    # Сводка внизу
    summary_parts = []
    if ticks:
        summary_parts.append(f"Ticks: {len(ticks)}")
    if fills:
        summary_parts.append(f"Fills: {len(fills)}")
    if rebuilds:
        summary_parts.append(f"Rebuilds: {len(rebuilds)}")
    if shifts:
        summary_parts.append(f"Shifts: {len(shifts)}")
    if pnl_values:
        summary_parts.append(f"Final PnL: {pnl_values[-1]:.8f}")
    if api_per_hour:
        summary_parts.append(f"Avg API req/h: {sum(api_per_hour)/len(api_per_hour):.0f}")
    if tick_ms_values:
        summary_parts.append(f"Avg tick: {sum(tick_ms_values)/len(tick_ms_values):.0f}ms")

    fig.text(
        0.5, 0.001,
        "  |  ".join(summary_parts),
        ha="center", fontsize=10, color="#888888",
    )

    plt.tight_layout(rect=[0, 0.02, 1, 0.98])

    # Экспорт в PNG
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
