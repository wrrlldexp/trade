#!/bin/bash
# MoneyBot — ежедневная очистка
# Запускается cron раз в сутки:
#   0 4 * * * /opt/moneybot/scripts/cleanup.sh >> /var/log/moneybot-cleanup.log 2>&1
#
# Очищает:
# 1. Docker-мусор (неиспользуемые образы, volumes, сети)
# 2. Старые логи мониторинга
# 3. Старые bot_logs в БД (>30 дней)

set -euo pipefail

COMPOSE_DIR="/opt/moneybot"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')] [cleanup]"

log() { echo "$LOG_PREFIX $1"; }

# ─── 1. Docker cleanup ───

cleanup_docker() {
    log "Очистка Docker-мусора..."
    docker system prune -f --filter "until=72h" 2>&1 | while read -r line; do log "  $line"; done
    log "Docker очистка завершена"
}

# ─── 2. Старые логи мониторинга ───

cleanup_logs() {
    log "Очистка старых логов мониторинга..."
    # Ротация логов мониторинга — оставляем последние 7 дней
    find /var/log -name "moneybot-*.log" -mtime +7 -delete 2>/dev/null || true
    log "Логи очищены"
}

# ─── 3. Старые bot_logs в БД ───

cleanup_db_logs() {
    log "Очистка старых bot_logs (>30 дней)..."
    cd "$COMPOSE_DIR"
    docker compose exec -T postgres psql -U moneybot -d moneybot \
        -c "DELETE FROM bot_logs WHERE created_at < NOW() - INTERVAL '30 days';" \
        2>&1 | while read -r line; do log "  $line"; done

    # Очистка старых audit_logs (>90 дней)
    docker compose exec -T postgres psql -U moneybot -d moneybot \
        -c "DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '90 days';" \
        2>&1 | while read -r line; do log "  $line"; done

    log "БД очищена"
}

# ─── Main ───

log "=== Запуск очистки ==="
cleanup_docker
cleanup_logs
cleanup_db_logs
log "=== Очистка завершена ==="
