# MoneyBot v2 — Работа с API бирж

## Поддерживаемые биржи

MoneyBot работает с **Binance** и **Bybit** через библиотеку [ccxt](https://github.com/ccxt/ccxt) — универсальный клиент для криптобирж.

| Биржа | Режимы | Тип | Тестнет |
|-------|--------|-----|---------|
| **Binance** | Spot | REST + WebSocket | testnet.binance.vision |
| **Bybit** | Spot | REST + WebSocket | testnet.bybit.com |

---

## Binance

### Получение API-ключей

1. Войдите на [binance.com](https://www.binance.com)
2. Перейдите: **Профиль** → **API Management** → **Create API**
3. Тип: **System generated**
4. Разрешения:
   - **Enable Spot & Margin Trading** — обязательно
   - **Enable Reading** — обязательно
   - **Enable Withdrawals** — **НЕ включать!**
5. IP Restrictions — рекомендуется ограничить IP сервера
6. Скопируйте **API Key** и **Secret Key**

> **Секрет показывается только один раз при создании!**

### Binance Testnet

1. Зарегистрируйтесь на [testnet.binance.vision](https://testnet.binance.vision)
2. Получите тестовые API-ключи (отличаются от основных!)
3. При добавлении аккаунта в MoneyBot включите флаг **Тестнет**

### Rate Limits (ограничения запросов)

| Тип лимита | Значение | Что считается |
|-----------|----------|---------------|
| **Request weight** | 1200 weight/мин | Каждый запрос имеет свой weight |
| **Order rate** | 10 ордеров/сек | Лимит на создание ордеров |
| **Raw requests** | 6100 за 5 мин | Общее количество запросов |

#### Weight основных операций

| Операция | Weight | Используется в |
|----------|--------|---------------|
| `GET /api/v3/ticker/price` | 1 | `get_ticker()` |
| `GET /api/v3/account` | 20 | `get_balance()` |
| `POST /api/v3/order` | 1 | `place_order()` |
| `DELETE /api/v3/order` | 1 | `cancel_order()` |
| `GET /api/v3/order` | 4 | `get_order_status()` |
| `GET /api/v3/openOrders` | 6 | `get_open_orders()` |

**Один тик сетки ~8 weight** (ticker + проверка + возможные ордера).

### Коды ошибок Binance

#### Retryable (MoneyBot автоматически повторит запрос)

| Код | Описание | Действие |
|-----|----------|----------|
| `-1003` | TOO_MANY_REQUESTS | Rate limit, ждём и повторяем |
| `-1015` | TOO_MANY_ORDERS | Лимит ордеров, ждём |
| `-1021` | TIMESTAMP_OUTSIDE_RECV_WINDOW | Рассинхрон часов, повторяем |

#### Permanent (ошибка логики, повтор не поможет)

| Код | Описание | Что делать |
|-----|----------|-----------|
| `-1022` | INVALID_SIGNATURE | Проверить API Secret |
| `-2010` | NEW_ORDER_REJECTED | Проверить параметры ордера (минимальный лот, цена) |
| `-2011` | CANCEL_REJECTED | Ордер уже отменён или исполнен |
| `-2013` | NO_SUCH_ORDER | Ордер не найден |
| `-2015` | INVALID_API_KEY | Ключ невалиден, отключён или истёк |

#### Другие частые ошибки

| Код | Описание | Решение |
|-----|----------|---------|
| `-1100` | Illegal characters | Проверить формат параметров |
| `-1013` | Filter failure | Объём или цена не прошли фильтр биржи |
| `-2008` | Insufficient balance | Недостаточно средств |

### Минимальные лоты (примеры)

| Пара | Мин. ордер | Мин. шаг цены | Мин. шаг количества |
|------|-----------|---------------|---------------------|
| BTC/USDT | 10 USDT | 0.01 | 0.00001 |
| ETH/USDT | 10 USDT | 0.01 | 0.0001 |
| SOL/USDT | 10 USDT | 0.01 | 0.01 |

> Точные значения проверяйте через `GET /api/v3/exchangeInfo` или в ccxt через `exchange.markets[symbol]`.

---

## Bybit

### Получение API-ключей

1. Войдите на [bybit.com](https://www.bybit.com)
2. Перейдите: **Профиль** → **API** → **Create New Key**
3. Тип: **System-generated API Keys**
4. Разрешения:
   - **Trade** (Spot) — обязательно
   - **Read** — обязательно
   - **Withdraw** — **НЕ включать!**
5. IP Restrictions — рекомендуется ограничить
6. Скопируйте **API Key** и **API Secret**

### Bybit Testnet

1. Зарегистрируйтесь на [testnet.bybit.com](https://testnet.bybit.com)
2. Получите тестовые API-ключи
3. При добавлении аккаунта в MoneyBot включите флаг **Тестнет**

### Rate Limits

| Тип лимита | Значение |
|-----------|----------|
| **API запросы** | 120 запросов/мин (спот) |
| **Ордера** | 100 ордеров/мин (спот) |
| **WebSocket подписки** | 100 на соединение |

### Коды ошибок Bybit

#### Retryable

| Код | Описание |
|-----|----------|
| `10006` | Rate limit exceeded |
| `10016` | Server error |
| `10018` | Service unavailable |

#### Permanent

| Код | Описание | Что делать |
|-----|----------|-----------|
| `10001` | Parameter error | Проверить параметры запроса |
| `10002` | Invalid request | Некорректный формат |
| `10003` | Invalid API key | Ключ невалиден |
| `10004` | Sign error | Проверить Secret |
| `110001` | Order not exists | Ордер не найден |
| `110007` | Insufficient balance | Недостаточно средств |
| `110012` | Insufficient available balance | Средства заблокированы |

---

## Как MoneyBot обрабатывает ошибки бирж

### Retry с экспоненциальной задержкой

Для retryable-ошибок бот автоматически:
1. Ждёт 1 секунду
2. Повторяет запрос
3. При неудаче — ждёт 2 секунды
4. При неудаче — ждёт 4 секунды
5. После 3 неудач — прекращает и логирует ошибку

Это реализовано в `CcxtExecutor` через декоратор `@retry_with_backoff()`.

### Permanent-ошибки

Бот **не** повторяет запрос, а:
1. Логирует ошибку с кодом в bot_logs
2. Возвращает результат `success=False` с описанием ошибки
3. Сетка продолжает работать (пропускает проблемный ордер)

### ccxt автоматические механизмы

ccxt (библиотека) сам:
- Включает rate limiting (`enableRateLimit: True`)
- Выставляет `recvWindow` для Binance (защита от clock skew)
- Автокоррекция timestamp (`adjustForTimeDifference: True`)
- Обрабатывает sandbox mode для тестнетов

---

## Рекомендации по безопасности API-ключей

1. **Никогда не включайте вывод средств** — для бота нужны только Trading и Reading
2. **IP Restrictions** — ограничьте IP вашего сервера на бирже
3. **Отдельные ключи** для каждого аккаунта/сетки
4. **Тестнет сначала** — всегда тестируйте на тестовой сети перед live
5. **При подозрении на утечку** — немедленно удалите ключ на бирже

---

## Торговые пары

### Binance — популярные пары для grid-торговли

| Пара | Волатильность | Ликвидность | Рекомендация |
|------|--------------|-------------|-------------|
| BTC/USDT | Средняя | Очень высокая | Основная пара, стабильная |
| ETH/USDT | Средняя-высокая | Очень высокая | Хорошая для grid |
| SOL/USDT | Высокая | Высокая | Больше сделок, больше риск |
| BNB/USDT | Средняя | Высокая | Стабильная пара |
| DOGE/USDT | Высокая | Высокая | Много движений, хороша для grid |

### Bybit — популярные пары

Аналогичный набор пар. Bybit поддерживает те же основные пары что и Binance.

### Как выбрать пару для grid-торговли

1. **Высокая ликвидность** — чтобы ордера исполнялись быстро
2. **Средняя волатильность** — слишком низкая = мало сделок, слишком высокая = высокий риск
3. **Маленький спред** — разница между bid и ask должна быть минимальной
4. **Стабильный боковой тренд** — grid-торговля наиболее эффективна в «коридоре»

---

## Полезные ссылки

### Binance
- API документация: `https://binance-docs.github.io/apidocs/spot/en/`
- Testnet: `https://testnet.binance.vision`
- Status page: `https://www.binance.com/en/support/announcement`

### Bybit
- API документация: `https://bybit-exchange.github.io/docs/v5/intro`
- Testnet: `https://testnet.bybit.com`
- Status page: `https://status.bybit.com`

### ccxt
- Документация: `https://docs.ccxt.com`
- Поддерживаемые биржи: `https://github.com/ccxt/ccxt#supported-cryptocurrency-exchange-markets`
