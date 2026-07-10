"""Сервис мониторинга — проверки здоровья системы.

Вызывается из:
- Cron-скрипта scripts/monitor.sh через API POST /api/bot/health-check
- Или напрямую из worker как периодическая задача
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field

import psutil

from app.core.notifier import notify


@dataclass
class HealthReport:
    """Результат проверки здоровья."""

    ok: bool = True
    checks: list[dict] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)

    def add_check(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append({"name": name, "status": status, "detail": detail})
        if status == "critical":
            self.ok = False
            self.alerts.append(f"{name}: {detail}")
        elif status == "warning":
            self.alerts.append(f"{name}: {detail}")

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checks": self.checks,
            "alerts": self.alerts,
        }


async def check_disk(threshold_warn: int = 80, threshold_crit: int = 90) -> dict:
    """Проверка свободного места на диске."""
    usage = shutil.disk_usage("/")
    used_pct = round(usage.used / usage.total * 100, 1)
    free_gb = round(usage.free / (1024**3), 1)

    if used_pct >= threshold_crit:
        return {"status": "critical", "detail": f"Диск заполнен на {used_pct}% (свободно {free_gb} GB)"}
    elif used_pct >= threshold_warn:
        return {"status": "warning", "detail": f"Диск заполнен на {used_pct}% (свободно {free_gb} GB)"}
    return {"status": "ok", "detail": f"Диск: {used_pct}% занято, {free_gb} GB свободно"}


async def check_memory(threshold_warn: int = 85, threshold_crit: int = 95) -> dict:
    """Проверка RAM."""
    mem = psutil.virtual_memory()
    used_pct = round(mem.percent, 1)
    available_mb = round(mem.available / (1024**2))

    if used_pct >= threshold_crit:
        return {"status": "critical", "detail": f"RAM: {used_pct}% (доступно {available_mb} MB)"}
    elif used_pct >= threshold_warn:
        return {"status": "warning", "detail": f"RAM: {used_pct}% (доступно {available_mb} MB)"}
    return {"status": "ok", "detail": f"RAM: {used_pct}%, доступно {available_mb} MB"}


async def check_cpu(threshold_warn: int = 80) -> dict:
    """Проверка CPU."""
    cpu_pct = psutil.cpu_percent(interval=1)
    if cpu_pct >= threshold_warn:
        return {"status": "warning", "detail": f"CPU: {cpu_pct}%"}
    return {"status": "ok", "detail": f"CPU: {cpu_pct}%"}


async def run_health_checks() -> HealthReport:
    """Запустить все проверки и отправить алерты."""
    report = HealthReport()

    # Диск
    disk = await check_disk()
    report.add_check("disk", disk["status"], disk["detail"])

    # RAM
    mem = await check_memory()
    report.add_check("memory", mem["status"], mem["detail"])

    # CPU
    cpu = await check_cpu()
    report.add_check("cpu", cpu["status"], cpu["detail"])

    # Отправляем алерты через notifier
    for alert_msg in report.alerts:
        level = "critical" if "critical" in alert_msg.lower() or not report.ok else "warning"
        await notify(
            f"Мониторинг: {alert_msg}",
            level=level,
            channel="monitoring",
        )

    return report
