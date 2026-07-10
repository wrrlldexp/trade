# MoneyBot v2

Торговый робот для автоматической сеточной торговли криптовалютами на **Binance** и **Bybit**, с backend на `FastAPI`, worker-процессом на Python и web-панелью на `React + Vite`.

## Возможности

- **6 торговых стратегий**: простая, капитализация, реверс, реверс+кап, адаптивная, адаптивная+кап
- **Binance и Bybit** (спот) через ccxt с retry и обработкой ошибок бирж
- **Paper и Live** режимы на каждой сетке (один код стратегии, разные исполнители)
- **Мониторинг**: логи бота в реальном времени, ошибки с traceback и source, история сделок
- **Управление ботом**: статус воркера, экстренная остановка всех сеток, перезагрузка
- **Дашборд**: графики PnL, распределение стратегий, метрики, позиции
- **Многопользовательский режим**: роли superadmin / admin / viewer
- **2FA** (TOTP — Google Authenticator, Authy)
- **Шифрование API-ключей** биржи (Fernet/AES)
- **Аудит**: журнал всех действий с IP и user-agent
- **WebSocket**: real-time стрим логов и событий сеток

## Стек

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0 async, Alembic, Redis, ccxt
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand
- **Infra**: Docker Compose, Makefile, PostgreSQL 16, Redis 7, Nginx

## Быстрый старт

```bash
make init          # создать .env + сгенерировать секреты
make up            # запустить все сервисы
make migrate       # применить миграции БД
make superadmin    # создать первого суперадмина
```

После запуска:

| Ресурс | URL |
|--------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Healthcheck | http://localhost:8000/health |

> Порты настраиваются через `.env`: `BACKEND_PORT`, `FRONTEND_PORT`

## Команды

```bash
make up                 # запустить все сервисы
make down               # остановить
make restart            # перезапустить
make logs               # логи всех сервисов
make logs-backend       # логи backend
make logs-worker        # логи worker
make ps                 # статус сервисов

make migrate            # применить миграции
make makemigration m="описание"   # создать миграцию
make superadmin         # создать суперадмина

make test               # тесты
make lint               # ruff + mypy
make format             # автоформатирование
make clean              # удалить контейнеры и volumes
```

## Локальный запуск без Docker

### Backend

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -e '.[dev]'
./.venv/bin/uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Продакшн-деплой

```bash
# Использовать prod-оверрайд:
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Подробности: [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md)

## Структура проекта

```
backend/
  app/
    api/          REST и WebSocket роутеры (auth, grids, accounts, users, audit, bot, logs, trades, dashboard, ws)
    core/         security, crypto, deps, audit, redis, bot_logger, error_middleware
    models/       SQLAlchemy модели (User, Grid, GridOrder, ExchangeAccount, AuditLog, TradeEvent, BotLog)
    schemas/      Pydantic-схемы API
    services/     оркестрация grid runtime
    strategy/     GridEngine, executors (Paper, ccxt/Binance/Bybit), typed contracts
  worker/         фоновая обработка сеток, heartbeat, команды
  cli/            CLI утилиты (create_superadmin)
  tests/          unit и API тесты

frontend/src/
  api/            axios client, endpoints, WebSocket hooks, типы
  components/     Layout, ProtectedRoute, UI компоненты
  pages/          Dashboard, Grids, Accounts, Users, Audit, Profile, Logs, Trades
  stores/         auth/theme stores
```

## Продакшн-чеклист

- [ ] Поменять все секреты в `.env` (`JWT_SECRET`, `ENCRYPTION_KEY`, `POSTGRES_PASSWORD`)
- [ ] Настроить домен, HTTPS (certbot) и nginx reverse proxy
- [ ] Включить резервное копирование PostgreSQL (`pg_dump`)
- [ ] Ограничить `CORS_ORIGINS` только своим доменом
- [ ] Включить 2FA для всех admin и superadmin
- [ ] Протестировать на Binance/Bybit Testnet перед live
- [ ] Настроить мониторинг (логи, healthcheck)

## Документация

| Документ | Описание |
|----------|----------|
| [Архитектура](./docs/ARCHITECTURE.md) | Схема, стек, БД, Redis-каналы |
| [Деплой](./docs/DEPLOYMENT.md) | VPS, Docker, nginx, SSL, systemd, бэкапы |
| [Безопасность](./docs/SECURITY.md) | Чеклист, API-ключи, инциденты |
| [Руководство пользователя](./docs/MANUAL_RU.md) | Полный мануал: стратегии, параметры, интерфейс |
| [Серверные требования](./docs/SERVERS.md) | Минимальные мощности, расчёт ресурсов |
| [API бирж](./docs/EXCHANGES_API.md) | Binance/Bybit API, лимиты, ошибки |
