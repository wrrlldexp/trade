# MoneyBot v2 — Пошаговое руководство по деплою

## Содержание

1. [Требования к серверу](#1-требования-к-серверу)
2. [Подготовка сервера](#2-подготовка-сервера)
3. [Установка Docker](#3-установка-docker)
4. [Клонирование и настройка](#4-клонирование-и-настройка)
5. [Генерация секретов](#5-генерация-секретов)
6. [Первый запуск](#6-первый-запуск)
7. [Создание суперадмина](#7-создание-суперадмина)
8. [Настройка SSL (Let's Encrypt)](#8-настройка-ssl-lets-encrypt)
9. [Настройка nginx для домена](#9-настройка-nginx-для-домена)
10. [Автозапуск через systemd](#10-автозапуск-через-systemd)
11. [Резервное копирование](#11-резервное-копирование)
12. [Обновление](#12-обновление)
13. [Мониторинг и логи](#13-мониторинг-и-логи)
14. [Устранение проблем](#14-устранение-проблем)
15. [Чеклист перед боевым запуском](#15-чеклист-перед-боевым-запуском)

---

## 1. Требования к серверу

| Параметр | Минимум | Рекомендуется |
|----------|---------|---------------|
| ОС | Ubuntu 22.04 / Debian 12 | Ubuntu 24.04 LTS |
| CPU | 2 vCPU | 4 vCPU (для 10+ сеток) |
| RAM | 4 GB | 8 GB |
| Диск | 20 GB SSD | 40 GB SSD |
| Порты | 22, 80, 443 | 22, 80, 443 |
| Docker | 24.0+ | 27.0+ |
| Docker Compose | v2.20+ | v2.29+ |

**Потребление ресурсов по контейнерам:**

| Сервис | RAM (лимит) | CPU (лимит) |
|--------|-------------|-------------|
| PostgreSQL | 512 MB | 1.0 |
| Redis | 128 MB | 0.5 |
| Backend (API) | 512 MB | 1.0 |
| Worker | 512 MB | 1.0 |
| Frontend | 256 MB | 0.5 |
| Nginx | 64 MB | 0.25 |
| **Итого** | **~2 GB** | **4.25 vCPU** |

Подробный расчёт нагрузки: [SERVERS.md](./SERVERS.md)

---

## 2. Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Базовые пакеты
sudo apt install -y git curl wget htop unzip

# Настройка файрвола (ufw)
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable

# Настройка swap (если RAM < 4 GB)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Создание пользователя (опционально, если работаете под root)
sudo adduser moneybot
sudo usermod -aG sudo moneybot
sudo su - moneybot
```

---

## 3. Установка Docker

```bash
# Установка Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Установка Docker Compose plugin
sudo apt-get install -y docker-compose-plugin

# ВАЖНО: перелогиниться, чтобы группа docker применилась
exit
# ssh user@server
```

**Проверка:**
```bash
docker --version          # Docker version 24+
docker compose version    # Docker Compose version v2+
```

---

## 4. Клонирование и настройка

```bash
# Клонирование репозитория
git clone <repo-url> /opt/moneybot
cd /opt/moneybot

# Создание .env из шаблона
cp .env.example .env
```

---

## 5. Генерация секретов

Выполните на сервере (или локально) — каждую команду отдельно:

```bash
# 1. Пароль PostgreSQL
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Пример: k7J9xBqR_mZ2Yd5aHtLpN3wFcQeV8sXu_0nIjGhKm

# 2. JWT Secret (для подписи токенов авторизации)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# Пример: aB3cD5eF7gH9iJ1kL3mN5oP7qR9sT1uV3wX5yZ7aB3cD5eF7gH9iJ1kL3m

# 3. Encryption Key (для шифрования API-ключей бирж, Fernet)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Пример: ZmFrZS1rZXktZm9yLWRvY3VtZW50YXRpb24tcHVycG9zZXM=
```

> **Если python3 не установлен** на сервере, можно сгенерировать локально и скопировать.
> Для Fernet-ключа нужна библиотека: `pip install cryptography`

**Заполните `.env`:**

```bash
nano /opt/moneybot/.env
```

```env
ENVIRONMENT=production

POSTGRES_USER=moneybot
POSTGRES_PASSWORD=<пароль_из_шага_1>
POSTGRES_DB=moneybot
POSTGRES_PORT=5432

REDIS_PORT=6379
BACKEND_PORT=8001
FRONTEND_PORT=5173

JWT_SECRET=<секрет_из_шага_2>
ENCRYPTION_KEY=<ключ_из_шага_3>

CORS_ORIGINS=https://your-domain.com
VITE_API_URL=https://your-domain.com
```

> **Замените `your-domain.com`** на ваш реальный домен. Если домена нет — используйте IP сервера:
> `CORS_ORIGINS=http://YOUR_SERVER_IP` и `VITE_API_URL=http://YOUR_SERVER_IP`

---

## 6. Первый запуск

```bash
cd /opt/moneybot

# Собрать и запустить в продакшн-режиме
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Первая сборка занимает 3–5 минут. Дождитесь завершения.

**Проверка статуса:**

```bash
docker compose ps
```

Все 6 сервисов должны быть в статусе `Up (healthy)` или `Up`:

```
NAME                 STATUS
moneybot_postgres    Up (healthy)
moneybot_redis       Up (healthy)
moneybot_backend     Up (healthy)
moneybot_worker      Up
moneybot_frontend    Up
moneybot_nginx       Up
```

**Проверка healthcheck API:**

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"moneybot-backend","version":"2.0.0","environment":"production"}
```

**Если что-то не поднялось:**
```bash
docker compose logs backend   # логи API
docker compose logs worker    # логи воркера
docker compose logs postgres  # логи БД
```

---

## 7. Создание суперадмина

```bash
docker compose exec backend python -m cli.create_superadmin
```

Следуйте инструкциям — укажите email и пароль. Пароль должен содержать минимум 8 символов, буквы и цифры.

**Проверка:** откройте `http://YOUR_SERVER_IP` в браузере и войдите с указанными данными.

> **После входа обязательно включите 2FA** (Профиль → Настройки 2FA).

---

## 8. Настройка SSL (Let's Encrypt)

### Вариант A: Certbot на хосте (рекомендуется)

```bash
# Установка certbot
sudo apt install -y certbot

# Остановка nginx (чтобы порт 80 был свободен для certbot)
docker compose stop nginx

# Получение сертификата
sudo certbot certonly --standalone -d your-domain.com

# Запуск nginx обратно
docker compose start nginx
```

Сертификаты будут в `/etc/letsencrypt/live/your-domain.com/`.

### Вариант B: Certbot в nginx-режиме (если внешний nginx на хосте)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
sudo certbot renew --dry-run  # проверка автообновления
```

---

## 9. Настройка nginx для домена

### С SSL (рекомендуется)

Отредактируйте `nginx/nginx.conf`:

1. Раскомментируйте HTTPS server block
2. Замените `your-domain.com` на ваш домен
3. Раскомментируйте redirect HTTP → HTTPS
4. Подключите volume сертификатов в `docker-compose.yml`:

```yaml
nginx:
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    - /etc/letsencrypt:/etc/nginx/ssl:ro
```

5. Перезапустите nginx:
```bash
docker compose restart nginx
```

### Без SSL (для теста / по IP)

Работает из коробки. Доступ по `http://YOUR_SERVER_IP`.

### Автообновление сертификата

```bash
# Добавить в cron
echo "0 2 * * * certbot renew --quiet && docker compose -f /opt/moneybot/docker-compose.yml restart nginx" | sudo crontab -
```

---

## 10. Автозапуск через systemd

Создайте `/etc/systemd/system/moneybot.service`:

```ini
[Unit]
Description=MoneyBot v2
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/moneybot
ExecStart=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose down
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable moneybot
sudo systemctl start moneybot

# Проверка
sudo systemctl status moneybot
```

Теперь MoneyBot автоматически запускается после перезагрузки сервера.

---

## 11. Резервное копирование

### Скрипт бэкапа

Создайте `/opt/moneybot/backup.sh`:

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/opt/moneybot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Начинаю бэкап..."

# Дамп PostgreSQL
docker compose -f /opt/moneybot/docker-compose.yml exec -T postgres \
  pg_dump -U moneybot moneybot | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Копия .env (содержит секреты!)
cp /opt/moneybot/.env "$BACKUP_DIR/env_$DATE"

# Удаление бэкапов старше 30 дней
find "$BACKUP_DIR" -type f -mtime +30 -delete

echo "[$(date)] Бэкап завершён: $BACKUP_DIR/db_$DATE.sql.gz"
```

```bash
chmod +x /opt/moneybot/backup.sh

# Добавить в cron (ежедневно в 3:00)
echo "0 3 * * * /opt/moneybot/backup.sh >> /opt/moneybot/backups/cron.log 2>&1" | sudo crontab -a -
```

### Восстановление из бэкапа

```bash
# Остановить воркер (чтобы не было записей во время восстановления)
docker compose stop worker

# Восстановить дамп
gunzip -c backups/db_20260514_030000.sql.gz | \
  docker compose exec -T postgres psql -U moneybot moneybot

# Запустить воркер
docker compose start worker
```

### Копирование бэкапов на внешнее хранилище

```bash
# rsync на другой сервер
rsync -avz /opt/moneybot/backups/ user@backup-server:/backups/moneybot/

# Или в S3
aws s3 sync /opt/moneybot/backups/ s3://your-bucket/moneybot-backups/
```

---

## 12. Обновление

```bash
cd /opt/moneybot

# 1. Сделать бэкап перед обновлением
./backup.sh

# 2. Стянуть обновления
git pull

# 3. Пересобрать и перезапустить
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 4. Применить новые миграции (если есть)
docker compose exec backend alembic upgrade head

# 5. Проверить
docker compose ps
curl http://localhost:8000/health
```

> **Внимание:** при обновлении работающие сетки будут приостановлены и автоматически восстановлены воркером (он подхватывает RUNNING сетки из БД при старте).

---

## 13. Мониторинг и логи

### Логи контейнеров

```bash
docker compose logs -f backend    # API сервер
docker compose logs -f worker     # торговый воркер
docker compose logs -f nginx      # reverse proxy
docker compose logs -f            # все сервисы
docker compose logs --tail=100 worker  # последние 100 строк
```

### Healthcheck API

```bash
# Здоровье backend
curl http://localhost:8000/health

# Статус воркера (нужен токен)
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/bot/status
# {"online":true,"active_grids":3,"grid_ids":[...],"last_seen":...}
```

### Web-интерфейс мониторинга

| Страница | Описание |
|----------|----------|
| `/dashboard` | Общая статистика, PnL, активные сетки |
| `/grids` | Управление сетками (запуск/стоп) |
| `/logs` | Real-time логи бота (WebSocket) |
| `/trades` | История торговых событий |
| `/audit` | Аудит действий пользователей (superadmin) |

### Мониторинг ресурсов

```bash
# Использование RAM/CPU контейнерами
docker stats --no-stream

# Размер базы данных
docker compose exec postgres psql -U moneybot -c "SELECT pg_database_size('moneybot') / 1024 / 1024 AS size_mb;"

# Размер Redis
docker compose exec redis redis-cli info memory | grep used_memory_human
```

---

## 14. Устранение проблем

### Backend не стартует

```bash
docker compose logs backend
# Частые причины:
# - Неверный DATABASE_URL → проверьте .env
# - Не применены миграции → docker compose exec backend alembic upgrade head
# - Порт занят → проверьте BACKEND_PORT в .env
```

### Worker offline (в интерфейсе показывает «оффлайн»)

```bash
docker compose logs worker
docker compose restart worker

# Проверить Redis
docker compose exec redis redis-cli GET worker:heartbeat
```

### Ошибка подключения к бирже

1. Проверьте API-ключи (правильная биржа, testnet/mainnet)
2. Проверьте IP-whitelist на бирже (добавьте IP сервера)
3. Сначала протестируйте в paper-режиме

### Сброс пароля суперадмина

```bash
docker compose exec backend python -m cli.create_superadmin
# Создаст нового или подскажет как сбросить
```

### Полная переустановка

```bash
cd /opt/moneybot
docker compose down -v          # удаляет контейнеры И тома (ДАННЫЕ БУДУТ ПОТЕРЯНЫ!)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m cli.create_superadmin
```

---

## 15. Чеклист перед боевым запуском

### Безопасность
- [ ] `.env` — все секреты заменены (`JWT_SECRET`, `ENCRYPTION_KEY`, `POSTGRES_PASSWORD`)
- [ ] Секреты НЕ попали в git (`.env` в `.gitignore`)
- [ ] `CORS_ORIGINS` — только ваш домен (не `*`)
- [ ] SSL-сертификат установлен и работает
- [ ] 2FA включена у всех admin/superadmin
- [ ] Файрвол настроен (только 22, 80, 443)
- [ ] Swagger UI скрыт в production (`ENVIRONMENT=production`)

### Инфраструктура
- [ ] `VITE_API_URL` — публичный URL через HTTPS
- [ ] Systemd unit включён (`systemctl enable moneybot`)
- [ ] Бэкапы настроены и работают (cron)
- [ ] Тестовый бэкап + восстановление выполнены

### Торговля
- [ ] Бот протестирован в paper-режиме
- [ ] Бот протестирован на testnet бирже
- [ ] API-ключи бирж с правильными разрешениями (только торговля, без вывода!)
- [ ] IP-whitelist на бирже настроен (IP сервера)
- [ ] Стартовая сетка с минимальным лотом для проверки на mainnet

### Мониторинг
- [ ] `curl /health` возвращает `{"status":"ok"}`
- [ ] Воркер онлайн (`/api/bot/status`)
- [ ] WebSocket логи работают (`/logs` в интерфейсе)
- [ ] Алерты настроены (uptime monitoring: UptimeRobot, Hetrixtools и т.д.)
