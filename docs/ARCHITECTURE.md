# MoneyBot v2 — Архитектура проекта

## 1. Краткое описание

Торговый робот, реализующий **сеточную торговлю криптовалютами** на биржах **Binance** и **Bybit** (спот), с веб-панелью управления.

**Ключевые возможности:**
- 6 торговых стратегий (простая, капитализация, реверс, реверс+кап, адаптивная, адаптивная+кап)
- Параллельные режимы: paper trading + реальная торговля (переключатель на каждой сетке)
- Поддержка Binance и Bybit через ccxt
- 2–5 администраторов с ролями (superadmin / admin / viewer)
- Несколько биржевых аккаунтов на одного админа
- 2FA-авторизация (TOTP)
- Мониторинг: логи бота, ошибки с traceback, история сделок
- Управление воркером: статус, остановка всех сеток, перезагрузка
- Дашборд с графиками и статистикой в реальном времени
- WebSocket: real-time стрим логов, события сеток

## 2. Стек технологий

### Backend
| Компонент | Технология | Версия |
|---|---|---|
| Язык | Python | >= 3.12 |
| Web-фреймворк | FastAPI | >= 0.115 |
| ORM | SQLAlchemy 2.0 (async) | >= 2.0.36 |
| Миграции | Alembic | >= 1.14 |
| БД | PostgreSQL | 16 |
| Pub/sub + кеш | Redis | 7 |
| Биржевой клиент | ccxt | >= 4.4 |
| Auth | JWT (python-jose) + passlib | - |
| 2FA | pyotp (TOTP) | >= 2.9 |
| Шифрование ключей | cryptography (Fernet/AES) | >= 43.0 |
| Логирование | structlog | >= 24.4 |
| Тесты | pytest + pytest-asyncio | - |
| Линтеры | ruff + mypy | - |

### Frontend
| Компонент | Технология | Версия |
|---|---|---|
| Framework | React + TypeScript | 18.3 / 5.6 |
| Build tool | Vite | 5.4 |
| Стили | Tailwind CSS | 3.4 |
| State | Zustand + TanStack Query | 5.0 / 5.59 |
| Роутинг | React Router | 6.28 |
| Графики | Recharts | 2.13 |
| Формы | React Hook Form + Zod | 7.53 / 3.23 |
| Иконки | lucide-react | 0.460 |

### Инфраструктура
- **Docker Compose** — 6 сервисов (postgres, redis, backend, worker, frontend, nginx)
- **Makefile** — 15+ команд
- **Nginx** — reverse proxy с поддержкой WebSocket и HTTPS

## 3. Архитектурная схема

```
┌─────────────────────────────────────────────────────────────────┐
│                          BROWSER                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │   React SPA (адаптивный, mobile-first)                    │   │
│  │   Страницы: Дашборд, Сетки, Аккаунты, Пользователи,      │   │
│  │             Аудит, Профиль, Логи, Сделки                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP / WebSocket (через nginx)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ /auth    │ │ /grids   │ │ /accounts│ │ /ws              │   │
│  │ login,2fa│ │ CRUD,    │ │ CRUD     │ │ /ws/grids/{id}   │   │
│  │ invite   │ │ start,   │ │ Binance  │ │ /ws/logs         │   │
│  │ register │ │ stop     │ │ + Bybit  │ │                  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ /users   │ │ /audit   │ │ /logs    │ │ /trades          │   │
│  │          │ │          │ │ бот-логи │ │ история сделок   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
│  ┌──────────┐ ┌──────────────────────────────────────────┐      │
│  │ /bot     │ │ Middleware: JWT, RBAC, audit,             │      │
│  │ status,  │ │ ErrorLoggingMiddleware (traceback→DB)     │      │
│  │ stop-all,│ │                                          │      │
│  │ restart  │ │                                          │      │
│  └──────────┘ └──────────────────────────────────────────┘      │
└──────┬──────────────────┬───────────────────┬──────────────────┘
       │                  │                   │
       ▼                  ▼                   ▼
  ┌─────────┐       ┌──────────┐        ┌──────────────┐
  │PostgreSQL│      │  Redis   │        │ Binance/Bybit│
  │  16      │      │  7       │        │    API       │
  │          │      │          │        │              │
  │ users    │      │ pub/sub: │        │  REST + WS   │
  │ accounts │      │  grids:  │        │  через ccxt  │
  │ grids    │      │  commands│        │              │
  │ orders   │      │  bot:logs│        │              │
  │ trades   │      │  grid:*  │        │              │
  │ audit    │      │  worker: │        │              │
  │ bot_logs │      │  control │        │              │
  │          │      │  heartbt │        │              │
  └──────────┘      └──────────┘        └──────────────┘
       ▲                  ▲                   ▲
       │                  │                   │
┌──────┴──────────────────┴───────────────────┴──────────────────┐
│                  Strategy Worker (отдельный процесс)            │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  CommandListener → GridEngine → Executor (Paper/Live)  │    │
│  │  (Redis pub/sub)   (6 стратегий) (ccxt Binance/Bybit)  │    │
│  └────────────────────────────────────────────────────────┘    │
│  Один воркер, сетки — asyncio tasks. Heartbeat каждые 10 сек.  │
│  Управляется через Redis (start/stop/restart).                 │
│  bot_logger → DB + Redis → WebSocket                           │
└────────────────────────────────────────────────────────────────┘
```

## 4. Docker-сервисы

| Сервис | Назначение |
|---|---|
| `postgres` | База данных (PostgreSQL 16) |
| `redis` | Pub/sub + heartbeat + fallback channel |
| `backend` | FastAPI (uvicorn) — REST/WebSocket API |
| `worker` | Стратегический воркер — крутит сетки, heartbeat |
| `frontend` | Vite dev-server (dev) / vite preview (prod) |
| `nginx` | Reverse proxy — API, WebSocket, статика |

## 5. Схема БД

```sql
-- Пользователи панели
users (
  id              uuid PK,
  email           varchar UNIQUE,
  password_hash   varchar,
  full_name       varchar,
  role            enum(superadmin, admin, viewer),
  totp_secret_enc bytea NULL,
  totp_enabled    bool DEFAULT false,
  is_active       bool DEFAULT true,
  created_by      uuid FK users NULL,
  created_at      timestamptz,
  last_login_at   timestamptz NULL
)

-- Приглашения
user_invites (
  id              uuid PK,
  email           varchar,
  role            enum(...),
  token           varchar UNIQUE,
  invited_by      uuid FK users,
  expires_at      timestamptz,
  used_at         timestamptz NULL,
  created_at      timestamptz
)

-- Биржевые аккаунты
exchange_accounts (
  id              uuid PK,
  owner_id        uuid FK users,
  name            varchar,
  exchange        varchar DEFAULT 'binance',
  api_key_enc     bytea,
  api_secret_enc  bytea,
  is_testnet      bool,
  is_active       bool DEFAULT true,
  created_at      timestamptz
)

-- Торговые сетки
grids (
  id                      uuid PK,
  account_id              uuid FK exchange_accounts,
  name                    varchar,
  symbol                  varchar,
  strategy                enum(simple, capitalization, reverse, reverse_cap, adaptive, adaptive_cap),
  mode                    enum(paper, live),
  status                  enum(draft, running, stopped, error),
  lot_size                numeric(20,8),
  profit_step             numeric(20,8),
  grid_step               numeric(20,8),
  levels_above            int,
  levels_below            int,
  rebuild_timeout_sec     int DEFAULT 3600,
  adaptive_timer_sec      int DEFAULT 15,
  prepay_base             numeric(20,8),
  prepay_quote            numeric(20,8),
  prepay_amount           numeric(20,8),
  adaptive_top_order_idx  int NULL,
  adaptive_bottom_order_idx int NULL,
  prepay_base_tail        numeric(20,8),
  prepay_quote_tail       numeric(20,8),
  last_boundary_hit_at    timestamptz NULL,
  total_trades            int DEFAULT 0,
  realized_pnl            numeric(20,8) DEFAULT 0,
  created_by              uuid FK users,
  created_at              timestamptz,
  started_at              timestamptz NULL,
  stopped_at              timestamptz NULL
)

-- Ордера сетки
grid_orders (
  id                  uuid PK,
  grid_id             uuid FK grids,
  grid_index          int,
  side                enum(buy, sell),
  status              enum(pending, placed, filled, cancelled, error, wait),
  price               numeric(20,8),
  price_sell          numeric(20,8),
  amount              numeric(20,8),
  prepay              numeric(20,8),
  re_buy              bool,
  re_sell             bool,
  profit              numeric(20,8),
  count_complete      int DEFAULT 0,
  exchange_order_id   varchar NULL,
  filled_at           timestamptz NULL,
  created_at          timestamptz,
  updated_at          timestamptz
)

-- История сделок
trade_events (
  id              bigserial PK,
  grid_id         uuid FK grids,
  event_type      enum(placed, filled, cancelled, flipped),
  price           numeric(20,8),
  amount          numeric(20,8),
  pnl_delta       numeric(20,8),
  payload         jsonb,
  created_at      timestamptz INDEX
)

-- Журнал аудита
audit_log (
  id              bigserial PK,
  user_id         uuid FK users NULL,
  action          varchar,
  entity_type     varchar,
  entity_id       varchar,
  ip_address      inet,
  user_agent      text,
  payload         jsonb,
  created_at      timestamptz INDEX
)

-- Логи бота
bot_logs (
  id              bigserial PK,
  level           enum(info, warning, error, critical) INDEXED,
  message         varchar(1000),
  source          varchar(500),
  grid_id         uuid FK grids SET NULL INDEXED,
  traceback       varchar(10000),
  payload         jsonb,
  created_at      timestamptz INDEXED
)
```

## 6. Модуль мониторинга

### bot_logger
Централизованный логгер бота (`app/core/bot_logger.py`):
- Автоматическое определение source (file:line:function) через `inspect.currentframe()`
- Запись в 3 канала: **console** (structlog) + **БД** (таблица bot_logs, отдельная сессия) + **Redis pub/sub** (канал `bot:logs`)
- Поддержка уровней: info, warning, error, critical
- При ошибке — полный traceback

### ErrorLoggingMiddleware
Middleware (`app/core/error_middleware.py`):
- Перехватывает все unhandled exceptions
- Извлекает source (file:line:function) из traceback
- Записывает через bot_logger в БД и Redis
- Возвращает JSON 500 клиенту

### WebSocket /ws/logs
- Real-time стрим логов через Redis pub/sub → WebSocket
- Fallback на локальный канал при отсутствии Redis

### Управление ботом (/api/bot)
- `GET /status` — онлайн/оффлайн, количество активных сеток, heartbeat
- `POST /stop-all` — экстренная остановка всех сеток (admin+)
- `POST /restart` — перезагрузка воркера (superadmin)

## 7. Логика стратегий

### 6 стратегий
| # | Стратегия | Описание |
|---|---|---|
| 1 | Простая (simple) | Фиксированный лот, buy→sell с profit_step |
| 2 | Капитализация (capitalization) | + реинвестирование прибыли в рост лота |
| 3 | Реверс (reverse) | Прибыль через отношение цен |
| 4 | Реверс+Кап (reverse_cap) | Реверс + капитализация |
| 5 | Адаптивная (adaptive) | Скользящая подсетка, prepay, reBuy/reSell |
| 6 | Адаптивная+Кап (adaptive_cap) | Адаптивная + капитализация |

### Архитектура стратегии
```
GridEngine (чистая логика, без I/O)
    ├── build_initial_grid(center_price) → GridState
    ├── tick(state, now) → GridState
    └── Использует Executor (абстрактный интерфейс)

Executor (интерфейс)
    ├── PaperExecutor — симуляция без биржи
    └── CcxtExecutor — реальная торговля через ccxt
        ├── Binance (retry: -1003, -1015, -1021)
        └── Bybit (retry: 10006, 10016, 10018)

GridService (оркестратор)
    ├── start_grid / stop_grid / tick_grid
    ├── Сохранение state в БД
    └── Redis pub/sub для координации с worker
```

## 8. Безопасность

| Угроза | Защита |
|---|---|
| Утечка пароля | bcrypt-хеши |
| Перехват сессии | JWT 15 мин access + 7 дней refresh |
| Захват аккаунта | 2FA (TOTP) для admin/superadmin |
| Утечка API-ключей | Fernet-шифрование, мастер-ключ из env |
| Открытая регистрация | Только по приглашению, первый суперадмин через CLI |
| Аудит | Лог всех действий: кто, когда, с какого IP |
| Brute force | Rate-limit на /login |
| XSS | React + CSP-заголовки |

## 9. Структура папок

```
moneybot-v2/
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile
├── README.md
├── .env.example
├── nginx/nginx.conf
│
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── alembic.ini
│   ├── migrations/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── enums.py
│   │   │   ├── user.py
│   │   │   ├── exchange_account.py
│   │   │   ├── grid.py
│   │   │   └── audit.py (AuditLog, TradeEvent, BotLog)
│   │   ├── schemas/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── grids.py
│   │   │   ├── accounts.py
│   │   │   ├── users.py
│   │   │   ├── audit.py
│   │   │   ├── bot.py
│   │   │   ├── dashboard.py
│   │   │   ├── logs.py
│   │   │   ├── trades.py
│   │   │   └── ws.py
│   │   ├── core/
│   │   │   ├── security.py
│   │   │   ├── crypto.py
│   │   │   ├── deps.py
│   │   │   ├── audit.py
│   │   │   ├── logging.py
│   │   │   ├── bot_logger.py
│   │   │   ├── error_middleware.py
│   │   │   └── redis_client.py
│   │   ├── services/
│   │   │   └── grid_service.py
│   │   └── strategy/
│   │       ├── engine.py
│   │       ├── types.py
│   │       ├── base_executor.py
│   │       ├── paper_executor.py
│   │       ├── live_executor.py
│   │       └── executors/
│   │           ├── ccxt_executor.py
│   │           └── base.py
│   ├── worker/
│   │   └── main.py
│   ├── cli/
│   │   └── create_superadmin.py
│   └── tests/
│
├── frontend/
│   ├── package.json
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── App.tsx
│       ├── api/
│       │   ├── client.ts
│       │   ├── types.ts
│       │   ├── ws.ts
│       │   ├── bot.ts
│       │   ├── logs.ts
│       │   └── trades.ts
│       ├── components/
│       │   └── Layout.tsx
│       ├── pages/
│       │   ├── Dashboard.tsx
│       │   ├── Grids.tsx
│       │   ├── Accounts.tsx
│       │   ├── Users.tsx
│       │   ├── Audit.tsx
│       │   ├── Profile.tsx
│       │   ├── Logs.tsx
│       │   └── Trades.tsx
│       └── stores/
│
└── docs/
    ├── ARCHITECTURE.md
    ├── DEPLOYMENT.md
    ├── SECURITY.md
    ├── MANUAL_RU.md
    ├── SERVERS.md
    └── EXCHANGES_API.md
```

## 10. Redis-каналы

| Канал | Назначение |
|---|---|
| `grids:commands` | Команды start/stop сеток (API → Worker) |
| `worker:control` | Управление воркером (stop_all, restart) |
| `worker:heartbeat` | Heartbeat воркера (key, TTL 30s) |
| `bot:logs` | Стрим логов бота → WebSocket /ws/logs |
| `grid:{id}:events` | События сетки → WebSocket /ws/grids/{id} |
