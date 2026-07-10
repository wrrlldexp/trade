#!/bin/bash
# Установка cron-задач для MoneyBot мониторинга
# Запустить один раз на сервере: bash /opt/moneybot/scripts/install-cron.sh

set -euo pipefail

SCRIPTS_DIR="/opt/moneybot/scripts"

# Сделать скрипты исполняемыми
chmod +x "$SCRIPTS_DIR/monitor.sh"
chmod +x "$SCRIPTS_DIR/cleanup.sh"

# Создать лог-файлы
touch /var/log/moneybot-monitor.log
touch /var/log/moneybot-cleanup.log

# Добавить cron-задачи (без дубликатов)
CRON_MONITOR="*/5 * * * * $SCRIPTS_DIR/monitor.sh >> /var/log/moneybot-monitor.log 2>&1"
CRON_CLEANUP="0 4 * * * $SCRIPTS_DIR/cleanup.sh >> /var/log/moneybot-cleanup.log 2>&1"

(crontab -l 2>/dev/null | grep -v "moneybot" ; echo "$CRON_MONITOR" ; echo "$CRON_CLEANUP") | crontab -

echo "Cron-задачи установлены:"
echo "  - Мониторинг: каждые 5 минут"
echo "  - Очистка: ежедневно в 04:00"
echo ""
echo "Проверить: crontab -l"
echo "Логи: tail -f /var/log/moneybot-monitor.log"
