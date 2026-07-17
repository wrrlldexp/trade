# MoneyBot v2

Торговый робот для автоматической сеточной торговли криптовалютами на **Binance** и **Bybit** (спот).  
Backend на **FastAPI**, event-driven worker на Python, web-панель на **React + Vite**.

---

## Содержание

- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Технологический стек](#технологический-стек)
- [Торговые стратегии](#торговые-стратегии)
- [Структура проекта](#структура-проекта)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [API](#api)
- [Worker — торговый движок](#worker--торговый-движок)
- [Reconciler — контроль целостности](#reconciler--контроль-целостности)
- [StatsCollector — сбор статистики](#statscollector--сбор-статистики)
- [Формулы расчётов](#формулы-расчётов)
- [Интерфейс](#интерфейс)
- [Безопасность](#безопасность)
- [Деплой](#деплой)
- [Команды разработки](#команды-разработки)
- [Документация](#документация)

---

## Возможности

### Торговля
- **6 торговых стратегий**: простая, капитализация, реверс, реверс+капитализация, адаптивная, адаптивная+капитализация
- **Binance и Bybit** (спот) через библиотеку ccxt с retry, rate-limit и обработкой ошибок бирж
- **Paper и Live** режимы — один и тот же код стратегии, разные исполнители
- **WebSocket** для мгновенного отслеживания исполненных ордеров (без задержки на поллинг)
- **Reconciler** — автоматическая сверка state бота с реальным состоянием ордеров на бирже
- **Адаптивный сдвиг сетки** при выходе цены за границы

### Мониторинг и аналитика
- **Дашборд**: сводка PnL, позиции, стратегии, балансы аккаунтов
- **Графики**: прибыль, курс, остаток (equity), просадка — для каждой сетки
- **StatsCollector**: снимки состояния каждые 60 секунд (курс, баланс, PnL, дрифт)
- **Логи бота** в реальном времени через WebSocket
- **История сделок** с фильтрацией по сетке, типу, периоду

### Управление
- **Многопользовательский режим**: роли ultraadmin / superadmin / admin / viewer
- **2FA** (TOTP — Google Authenticator, Authy)
- **Шифрование API-ключей** биржи (Fernet/AES)
- **Аудит**: журнал всех действий с IP и user-agent
- **Управление ботом**: статус воркера, экстренная остановка всех сеток

---

## Архитектура

```
                          ┌──────────────┐
                          │   Nginx      │ :80/:443
                          │ reverse proxy│
                          └──────┬───────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
              ┌─────▼─────┐           ┌───────▼──────┐
              │  Frontend  │           │   Backend    │
              │ React+Vite │           │   FastAPI    │ :8000
              │    :5173   │           │  REST + WS   │
              └────────────┘           └──────┬───────┘
                                              │
                                     ┌────────┴────────┐
                                     │                 │
                               ┌─────▼─────┐    ┌─────▼─────┐
                               │ PostgreSQL │    │   Redis    │
                               │    :5432   │    │   :6379    │
                               │ Данные,    │    │ pub/sub,   │
                               │ ордера,    │    │ команды,   │
                               │ логи       │    │ кэш        │
                               └────────────┘    └─────┬──────┘
                                                       │
                                                 ┌─────▼─────┐
                                                 │   Worker   │
                                                 │ Торговый   │
                                                 │ движок     │
                                                 │            │
                                                 │ ┌────────┐ │
                                                 │ │GridEng.│ │
                                                 │ ├────────┤ │
                                                 │ │Reconc. │ │
                                                 │ ├────────┤ │
                                                 │ │Stats   │ │
                                                 │ │Collect.│ │
                                                 │ └────────┘ │
                                                 │     │       │
                                                 │  ┌──▼──┐   │
                                                 │  │ccxt  │   │
                                                 │  │WS+API│   │
                                                 │  └──┬───┘   │
                                                 └─────┼───────┘
                                                       │
                                              ┌────────▼────────┐
                                              │  Binance / Bybit│
                                              │    Exchange API  │
                                              └─────────────────┘
```

### Потоки данных

| Поток | Описание |
|-------|----------|
| **Пользователь → Frontend → Backend** | Создание/запуск/остановка сеток, управление аккаунтами |
| **Backend → Redis → Worker** | Команды (start/stop) через pub/sub канал `grids:commands` |
| **Worker → Exchange** | Размещение и отмена ордеров через ccxt |
| **Exchange → Worker (WS)** | Мгновенные уведомления об исполнении ордеров |
| **Worker → Redis → Frontend (WS)** | Логи и события в реальном времени через канал `bot:logs` |
| **Worker → PostgreSQL** | Персистенция state, ордеров, статистики |

---

## Технологический стек

### Backend

| Технология | Версия | Назначение |
|-----------|--------|-----------|
| Python | 3.12+ | Язык |
| FastAPI | 0.115 | REST API + WebSocket |
| SQLAlchemy | 2.0 | ORM (async) |
| Alembic | 1.14 | Миграции БД |
| ccxt | 4.4 | API бирж (20+ бирж) |
| Redis | 5.2 | Pub/sub, кэш, rate limit |
| Pydantic | 2.10 | Валидация данных |
| Structlog | 24.4 | Структурированное логирование |
| PyOTP | 2.9 | TOTP 2FA |
| Passlib + bcrypt | — | Хэширование паролей |
| Matplotlib | 3.9 | Генерация отчётов (PNG) |

### Frontend

| Технология | Версия | Назначение |
|-----------|--------|-----------|
| React | 18.3 | UI framework |
| TypeScript | 5.6 | Типизация |
| Vite | 5.4 | Сборщик |
| Tailwind CSS | 3.4 | Стили |
| TanStack Query | 5.59 | Кэширование запросов |
| Zustand | 5.0 | Состояние |
| Recharts | 2.13 | Графики |
| Lightweight Charts | 5.2 | Свечные графики |
| React Hook Form + Zod | — | Формы + валидация |
| Framer Motion | 12.40 | Анимации |

### Инфраструктура

| Компонент | Версия | Назначение |
|-----------|--------|-----------|
| PostgreSQL | 16 | Основная БД |
| Redis | 7 | Pub/sub + кэш |
| Nginx | alpine | Reverse proxy, SSL |
| Docker Compose | — | Оркестрация |

---

## Торговые стратегии

Все стратегии работают по одному принципу: **сетка ордеров** с фиксированным шагом. Разница — в том, как обрабатывается прибыль после завершения цикла buy→sell.

### 1. Simple (Простая)

Базовая стратегия. Покупает на падении, продаёт на росте. Прибыль фиксируется в USDT, лот пересчитывается по текущей цене.

```
BUY @ 60000  →  SELL @ 60150  →  прибыль 150 USDT (минус комиссия)
                                  →  новый BUY @ 60000
```

### 2. Capitalization (Капитализация)

Вся прибыль реинвестируется в следующий лот. Лот растёт с каждым циклом.

```
Цикл 1: BUY 0.001 BTC  →  SELL  →  прибыль 0.15 USDT
Цикл 2: BUY 0.00100234 BTC  →  SELL  →  прибыль 0.1502 USDT
```

### 3. Reverse (Реверс)

Прибыль считается в **базовой** валюте (BTC). Используется для накопления крипты.

```
BUY @ 60000 → SELL @ 60150 → прибыль в BTC = net_quote / price_buy
```

### 4. Reverse Capitalization (Реверс + Капитализация)

Комбинация: прибыль в базовой валюте + реинвестиция в следующий лот.

### 5. Adaptive (Адаптивная)

Как простая, но при выходе цены за границы сетки — **сдвигает всю сетку** (shift) вслед за ценой, вместо полной перестройки. Быстрее реагирует на трендовое движение.

```
Цена ↑ за max сетки → shift_grid(delta=+Δ) → все ордера сдвинуты вверх
Цена ↓ за min сетки → shift_grid(delta=-Δ) → все ордера сдвинуты вниз
```

### 6. Adaptive Capitalization (Адаптивная + Капитализация)

Адаптивный сдвиг + реинвестиция прибыли в увеличение лота.

### Параметры сетки

| Параметр | Описание | Пример |
|----------|----------|--------|
| `grid_step` | Шаг между уровнями (USDT) | 80 |
| `profit_step` | Маржа прибыли (USDT) | 150 |
| `lot_size` | Размер лота (базовая валюта) | 0.001 BTC |
| `lot_quote` | Размер лота (котировочная валюта) | 8 USDT |
| `levels_above` | Кол-во уровней выше центра | 4 |
| `levels_below` | Кол-во уровней ниже центра | 30 |
| `rebuild_timeout_sec` | Таймаут перестройки при выходе за границы | 3600 |

> **Важно**: `profit_step` должен быть больше `fee × (price_buy + price_sell)`. Для BTC (~64000 USDT) при комиссии 0.1% минимальный profit_step ≈ 128 USDT. Иначе комиссия съедает всю прибыль.

---

## Структура проекта

```
trade/
├── backend/
│   ├── app/
│   │   ├── api/                    # REST + WebSocket роутеры
│   │   │   ├── auth.py             #   Авторизация, 2FA, инвайты
│   │   │   ├── grids.py            #   CRUD сеток, графики, статистика
│   │   │   ├── accounts.py         #   Биржевые аккаунты
│   │   │   ├── dashboard.py        #   Сводный дашборд + аналитика
│   │   │   ├── trades.py           #   История сделок
│   │   │   ├── logs.py             #   Логи бота
│   │   │   ├── users.py            #   Управление пользователями
│   │   │   ├── audit.py            #   Аудит действий
│   │   │   ├── bot.py              #   Управление ботом
│   │   │   ├── market.py           #   Рыночные данные (OHLCV, тикеры)
│   │   │   └── ws.py               #   WebSocket стрим логов
│   │   │
│   │   ├── core/                   # Инфраструктурный слой
│   │   │   ├── security.py         #   JWT, bcrypt, токены
│   │   │   ├── crypto.py           #   Шифрование API-ключей (Fernet)
│   │   │   ├── deps.py             #   Зависимости FastAPI (авторизация)
│   │   │   ├── redis_client.py     #   Redis pub/sub, кэш
│   │   │   ├── bot_logger.py       #   Логирование в БД + Redis
│   │   │   ├── grid_activity_logger.py  # Логи активности сеток
│   │   │   └── audit.py            #   Функция аудита действий
│   │   │
│   │   ├── models/                 # SQLAlchemy ORM модели
│   │   │   ├── grid.py             #   Grid, GridOrder
│   │   │   ├── user.py             #   User
│   │   │   ├── exchange_account.py #   ExchangeAccount
│   │   │   ├── stats.py            #   GridStatSnapshot, AccountStatSnapshot
│   │   │   ├── audit.py            #   AuditLog, BotLog, TradeEvent, GridActivityLog
│   │   │   └── enums.py            #   Все enum-типы
│   │   │
│   │   ├── services/               # Бизнес-логика
│   │   │   ├── grid_service.py     #   Жизненный цикл сеток (start/stop/tick)
│   │   │   ├── stats_collector.py  #   Сбор статистики (60-сек интервал)
│   │   │   ├── stats_query.py      #   Запрос метрик из снапшотов
│   │   │   └── monitor.py          #   Мониторинг здоровья воркера
│   │   │
│   │   └── strategy/               # Торговое ядро
│   │       ├── engine.py           #   GridEngine — логика всех 6 стратегий
│   │       ├── types.py            #   GridParams, GridState, LiveOrder, Ticker
│   │       ├── executor.py         #   Абстракция исполнителя
│   │       ├── base_executor.py    #   Базовый класс
│   │       ├── ccxt_executor.py    #   Реальная биржа через ccxt
│   │       ├── paper_executor.py   #   Эмуляция (paper trading)
│   │       ├── reconciler.py       #   GridReconciler — сверка state↔биржа
│   │       └── ws_stream.py        #   WebSocket поток ордеров
│   │
│   ├── worker/                     # Фоновый процесс
│   │   └── main.py                 #   Event loop, WS подключения, тики
│   │
│   ├── migrations/                 # Alembic миграции
│   │   └── versions/               #   0001..0011
│   │
│   ├── tests/                      # Тесты
│   │   └── services/               #   Unit-тесты stats_collector, stats_query
│   │
│   └── cli/                        # CLI утилиты
│       └── create_superadmin.py    #   Создание первого суперадмина
│
├── frontend/
│   └── src/
│       ├── api/                    # API клиенты (axios)
│       │   ├── client.ts           #   Axios instance + auth interceptor
│       │   ├── grids.ts            #   Грид CRUD + графики
│       │   ├── dashboard.ts        #   Дашборд + аналитика
│       │   ├── auth.ts             #   Логин, 2FA, refresh
│       │   └── ws.ts               #   WebSocket подключение
│       │
│       ├── pages/                  # Страницы
│       │   ├── Dashboard.tsx       #   Сводная панель
│       │   ├── GridList.tsx        #   Список сеток
│       │   ├── GridCreate.tsx      #   Создание сетки
│       │   ├── GridDetail.tsx      #   Детали сетки + ордера
│       │   ├── GridCharts.tsx      #   Графики сетки
│       │   ├── Chart.tsx           #   Свечной график
│       │   ├── Accounts.tsx        #   Биржевые аккаунты
│       │   ├── Trades.tsx          #   История сделок
│       │   ├── Logs.tsx            #   Логи бота
│       │   ├── Monitoring.tsx      #   Мониторинг воркера
│       │   ├── Users.tsx           #   Управление пользователями
│       │   ├── Audit.tsx           #   Аудит
│       │   ├── Profile.tsx         #   Профиль + 2FA
│       │   └── Login.tsx           #   Авторизация
│       │
│       ├── components/             # UI компоненты
│       └── store/                  # Zustand сторы (auth, theme)
│
├── nginx/                          # Конфигурация reverse proxy
├── docs/                           # Документация
├── docker-compose.yml              # Dev-окружение
├── docker-compose.prod.yml         # Продакшн-оверрайд
└── Makefile                        # Команды разработки
```

---

## Быстрый старт

### Требования

- Docker + Docker Compose
- Git

### Установка

```bash
git clone https://github.com/wrrlldexp/trade.git
cd trade

make init          # создать .env + сгенерировать секреты
make up            # запустить все сервисы
make migrate       # применить миграции БД
make superadmin    # создать первого суперадмина
```

### Доступ

| Ресурс | URL |
|--------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Healthcheck | http://localhost:8000/health |

> Порты настраиваются через `.env`: `BACKEND_PORT`, `FRONTEND_PORT`

### Первые шаги

1. Войти под суперадмином
2. Добавить биржевой аккаунт (Accounts → Добавить) — ввести API key/secret
3. Создать сетку (Grids → Создать) — выбрать символ, стратегию, параметры
4. Запустить в **Paper** режиме для теста
5. Переключить на **Live** после проверки

---

## Конфигурация

### Переменные окружения (.env)

| Переменная | Описание | Пример |
|-----------|----------|--------|
| `DATABASE_URL` | PostgreSQL строка подключения | `postgresql+asyncpg://moneybot:pass@postgres/moneybot` |
| `REDIS_URL` | Redis подключение | `redis://redis:6379/0` |
| `JWT_SECRET` | Секрет для JWT токенов | `случайная строка 64 символа` |
| `ENCRYPTION_KEY` | Ключ шифрования API-ключей | `Fernet ключ (44 символа)` |
| `CORS_ORIGINS` | Разрешённые домены | `http://localhost:5173` |
| `ENVIRONMENT` | Окружение | `production` / `development` |
| `GRID_RECONCILER_MODE` | Режим reconciler | `off` / `dry_run` / `active` |

### Режимы Reconciler

| Режим | Описание |
|-------|----------|
| `off` | Reconciler отключён |
| `dry_run` | Только логирует расхождения, не исправляет |
| `active` | Автоматически исправляет расхождения state↔биржа |

---

## API

### Аутентификация

```
POST /api/auth/login          # логин → access + refresh токен
POST /api/auth/refresh        # обновление токена
POST /api/auth/logout         # инвалидация токена
POST /api/auth/2fa/setup      # настройка TOTP
POST /api/auth/2fa/verify     # подтверждение 2FA
POST /api/auth/accept-invite  # принять инвайт
```

### Сетки

```
GET    /api/grids/                    # список сеток
POST   /api/grids/                    # создать сетку
GET    /api/grids/{id}                # детали сетки
PATCH  /api/grids/{id}                # обновить параметры
DELETE /api/grids/{id}                # удалить сетку
POST   /api/grids/{id}/start          # запустить сетку
POST   /api/grids/{id}/stop           # остановить сетку
GET    /api/grids/{id}/charts?hours=24    # графики (PnL, курс, equity, просадка)
GET    /api/grids/{id}/stats              # метрики (earnings, drift, drawdown)
GET    /api/grids/{id}/stats/series?hours=24  # временные ряды снапшотов
GET    /api/grids/{id}/report?hours=24    # PNG-отчёт
```

### Аккаунты

```
GET    /api/accounts/             # список аккаунтов
POST   /api/accounts/             # добавить аккаунт
PATCH  /api/accounts/{id}         # обновить
DELETE /api/accounts/{id}         # удалить
GET    /api/accounts/balances     # балансы всех аккаунтов
POST   /api/accounts/test         # тест подключения
```

### Дашборд и аналитика

```
GET    /api/dashboard/                   # сводка: PnL, позиции, стратегии
GET    /api/dashboard/analytics?days=30  # аналитика: PnL серии, drawdown, сравнение
```

### Прочее

```
GET    /api/trades/        # история сделок (фильтры: grid, type, date)
GET    /api/logs/          # логи бота (фильтры: level, grid, search)
GET    /api/users/         # пользователи (superadmin)
GET    /api/audit/         # аудит действий
GET    /api/bot/status     # статус воркера
POST   /api/bot/emergency-stop   # экстренная остановка всех сеток
GET    /api/market/ohlcv   # свечи (OHLCV)
GET    /api/market/ticker  # текущая цена
WS     /ws/logs            # WebSocket стрим логов
```

---

## Worker — торговый движок

Worker — это отдельный процесс, который управляет торговлей. Запускается в контейнере `moneybot_worker`.

### Event-driven архитектура

```
┌─────────────────────────────────────────────────────┐
│                     Worker                           │
│                                                      │
│  ┌──────────────┐     ┌──────────────┐               │
│  │ WS Stream    │────▶│ process_ws_  │──▶ on_order_  │
│  │ (Binance/    │     │ fill()       │    filled()   │
│  │  Bybit)      │     │ ~200ms       │    + flip     │
│  └──────────────┘     └──────────────┘               │
│                                                      │
│  ┌──────────────┐     ┌──────────────┐               │
│  │ Tick loop    │────▶│ tick_grid()  │──▶ reconcile  │
│  │ (30 сек)     │     │ fallback     │    + persist  │
│  └──────────────┘     └──────────────┘               │
│                                                      │
│  ┌──────────────┐     ┌──────────────┐               │
│  │ Redis sub    │────▶│ handle_cmd() │──▶ start/stop │
│  │ (commands)   │     │              │    grid       │
│  └──────────────┘     └──────────────┘               │
│                                                      │
│  ┌──────────────┐                                    │
│  │ Stats        │──▶ snapshot каждые 60 сек           │
│  │ Collector    │                                    │
│  └──────────────┘                                    │
└──────────────────────────────────────────────────────┘
```

### Два пути обработки fills

1. **WebSocket (быстрый путь)** — биржа отправляет событие исполнения ордера через WS → `process_ws_fill()` обрабатывает за ~200мс → ставит зеркальный ордер (flip)
2. **Tick (fallback)** — каждые 30 секунд `tick_grid()` проверяет все ордера через REST API → находит исполненные → обрабатывает

### Жизненный цикл сетки

```
DRAFT → start_grid() → RUNNING → worker._ensure_runtime()
    → build_initial_grid() → размещение ордеров на бирже
    → tick loop + WS stream → обработка fills
    → stop_grid() → отмена всех ордеров → STOPPED
```

---

## Reconciler — контроль целостности

`GridReconciler` сверяет внутренний state бота с реальным состоянием ордеров на бирже. Запускается на каждом тике (30 сек).

### Типы проверок

| Проверка | Проблема | Решение |
|----------|----------|---------|
| **Orphans** | Ордер на бирже есть, в state нет | Отменяет на бирже |
| **Ghosts** | В state PLACED, на бирже нет | Проверяет статус → fill или cancel |
| **Stale cancels** | В state CANCELLED, на бирже жив | Повторно отменяет |
| **Lost levels** | grid_index без PLACED ордера | Детектирует (не восстанавливает) |
| **Bloat** | Накопление filled/cancelled в state | Чистит (только placed остаются) |

### Режимы

- **off** — отключён
- **dry_run** — только логирует расхождения
- **active** — автоматически исправляет

---

## StatsCollector — сбор статистики

Каждые 60 секунд записывает снимок состояния каждой работающей сетки:

| Метрика | Описание |
|---------|----------|
| `course` | Текущий курс (mid price) |
| `profit_math` | Кумулятивная прибыль (realized_pnl) |
| `net_asset` | Остаток: фиат + крипта × курс |
| `net_asset_sag` | Дельта с предыдущего замера |
| `profit_drift` | Расхождение: profit_math - (net_asset - start_amount) |
| `total_trades` | Количество завершённых циклов |
| `placed_orders` | Количество активных ордеров |

---

## Формулы расчётов

### Прибыль нарастающим остатком

```
PnL = 0 + profit_cycle_1 + profit_cycle_2 + ... + profit_cycle_N
```

Где `profit_cycle` = чистая прибыль одного цикла buy→sell за вычетом комиссий:

```
gross = amount × profit_step
fee_cost = fee × amount × (price_buy + price_sell)
net = gross - fee_cost
```

> Если `net ≤ 0` — прибыль = 0 (комиссия больше заработка)

### Остаток (Equity)

```
Остаток = фиатный_остаток + вся_крипта × текущий_курс
```

В коде:
- **StatsCollector**: `net_asset = base_total × price + quote_total` (точно, раз в 60 сек)
- **Tick equity**: `placed_value + realized_pnl` (приближение, каждый тик)

### Просадка

```
Просадка = Остаток - Стартовый_объём
```

Где `Стартовый_объём` — сумма средств, замороженных при создании сетки (поле `grid.start_amount`).

### Стартовый объём

```
start_amount = Σ(price × amount) для BUY ордеров
             + Σ(amount × center_price) для SELL ордеров
```

Вычисляется один раз при `build_initial_grid()` и сохраняется в БД.

### Минимальный profit_step

```
profit_step > fee × (price_buy + price_sell)
```

Для BTC (~64000 USDT) при fee=0.001 (0.1%):
```
profit_step > 0.001 × (64000 + 64150) = 128.15 USDT
```

Рекомендация: `profit_step ≥ 150` для BTC.

---

## Интерфейс

### Страницы

| Страница | Описание |
|----------|----------|
| **Dashboard** | Сводка: PnL, активные сетки, позиции, графики equity и drawdown |
| **Grids** | Список сеток с фильтрами по статусу и стратегии |
| **Grid Detail** | Параметры сетки, список ордеров, статистика |
| **Grid Charts** | 4 графика: прибыль, курс (bid/ask), остаток, просадка |
| **Chart** | Свечной график (OHLCV) для любого символа |
| **Accounts** | Биржевые аккаунты с балансами |
| **Trades** | История сделок с фильтрами |
| **Logs** | Логи бота в реальном времени (WebSocket) |
| **Monitoring** | Статус воркера, heartbeat, активные сетки |
| **Users** | Управление пользователями, инвайты |
| **Audit** | Журнал действий |
| **Profile** | Настройки профиля, смена пароля, 2FA |

---

## Безопасность

- **JWT** токены (access 30 мин + refresh 7 дней) с blacklist в Redis
- **2FA (TOTP)** — Google Authenticator / Authy
- **Шифрование API-ключей** — Fernet (AES-128-CBC) с ключом из env
- **RBAC** — 4 роли: ultraadmin → superadmin → admin → viewer
- **CORS** — ограничение по доменам
- **Rate limiting** — через Redis
- **Аудит** — все действия логируются с IP и user-agent
- **Инвайты** — регистрация только по приглашению суперадмина

---

## Деплой

### Docker Compose (продакшн)

```bash
# Сборка и запуск
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Миграции
docker exec moneybot_backend alembic upgrade head

# Проверка
docker ps --format "{{.Names}}: {{.Status}}"
```

### Обновление на сервере

```bash
cd /opt/moneybot
git pull
docker compose build backend worker
docker compose up -d backend worker
docker exec moneybot_backend alembic upgrade head
docker restart moneybot_nginx
```

### Продакшн-чеклист

- [ ] Сменить все секреты в `.env` (`JWT_SECRET`, `ENCRYPTION_KEY`, `POSTGRES_PASSWORD`)
- [ ] Настроить домен + HTTPS (certbot) + nginx
- [ ] Включить резервное копирование PostgreSQL (`pg_dump`)
- [ ] Ограничить `CORS_ORIGINS` только своим доменом
- [ ] Включить 2FA для всех admin/superadmin
- [ ] Протестировать на Testnet перед live
- [ ] Настроить мониторинг (healthcheck, логи)
- [ ] Установить `GRID_RECONCILER_MODE=active`

---

## Команды разработки

```bash
# Сервисы
make up                 # запустить все
make down               # остановить
make restart            # перезапустить
make logs               # логи всех сервисов
make logs-backend       # логи backend
make logs-worker        # логи worker
make ps                 # статус

# База данных
make migrate            # применить миграции
make makemigration m="описание"   # создать миграцию
make superadmin         # создать суперадмина

# Разработка
make test               # запустить тесты
make lint               # ruff + mypy
make format             # автоформатирование
make clean              # удалить контейнеры и volumes
```

### Локальная разработка без Docker

```bash
# Backend
cd backend
python3 -m venv .venv
./.venv/bin/pip install -e '.[dev]'
./.venv/bin/uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

## Документация

| Документ | Описание |
|----------|----------|
| [Архитектура](./docs/ARCHITECTURE.md) | Схема системы, стек, БД, Redis-каналы |
| [Деплой](./docs/DEPLOYMENT.md) | VPS, Docker, nginx, SSL, systemd, бэкапы |
| [Безопасность](./docs/SECURITY.md) | Чеклист безопасности, API-ключи, инциденты |
| [Руководство пользователя](./docs/MANUAL_RU.md) | Полный мануал: стратегии, параметры, интерфейс |
| [Серверные требования](./docs/SERVERS.md) | Минимальные мощности, расчёт ресурсов |
| [API бирж](./docs/EXCHANGES_API.md) | Binance/Bybit API, лимиты, типичные ошибки |

---

## Лицензия

Проприетарное ПО. Все права защищены.
