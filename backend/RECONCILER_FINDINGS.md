# Reconciler Findings

## 1. Что уже было в воркере

### Существующий reconciliation-цикл (30 сек)
Worker (`worker/main.py`) вызывает `tick_grid()` каждые 30 секунд при WS-соединении (или 1 сек без WS). `engine.tick()` делает **один** `get_open_orders()` и находит пропавшие ордера — проверяет через `get_order_status()`, обрабатывает FILLED, помечает CANCELLED.

**Что tick покрывал:** обнаружение fills по пропавшим из open orders ордерам.
**Что tick НЕ покрывал:** orphans, stale cancels, lost levels, bloat.

### `_ensure_runtime()` — при старте/рестарте
Отменяет осиротевшие ордера на бирже перед построением сетки (sweep через `get_open_orders()`). Это разовая очистка, не continuous monitoring.

### `stop_grid()` — двойная зачистка
1. Отменяет все PLACED из state
2. Sweep через `get_open_orders()` — добивает остатки

### WebSocket — instant fills
`process_ws_fill()` обрабатывает fill мгновенно через WS-стрим с lock-защитой.

### Как развёл ответственность

| Задача | До reconciler | После reconciler |
|---|---|---|
| Fill detection (PLACED → missing) | `engine.tick()` | `engine.tick()` (без изменений) |
| Orphans (на бирже, нет в state) | Только при старте/стопе | **Reconciler: каждые 30 сек** |
| Stale cancels (CANCELLED но живой) | Не было | **Reconciler** |
| Ghost fills (PLACED, нет на бирже, FILLED) | `engine.tick()` (пересечение) | `engine.tick()` + reconciler (двойная сетка безопасна: tick проверяет первым, reconciler ловит оставшееся) |
| Lost levels | Не было | **Reconciler** (только детекция) |
| Bloat cleanup | Не было | **Reconciler** |

Reconciler запускается **после** `engine.tick()` в том же цикле — ловит то, что tick пропустил. Дублирование ghost-обработки безопасно: tick уже пометил found ghosts как CANCELLED/FILLED, reconciler видит только оставшиеся.

## 2. Формат ошибок executor

### `cancel_order(exchange_order_id: str) -> bool`
- `True` = успешно отменён
- `False` = `OrderNotFound` или permanent error (ордера уже нет)
- Exception = retryable error (сетевой сбой после исчерпания ретраёв)

**Коды ошибок не доступны** на уровне интерфейса. CcxtExecutor обрабатывает коды внутри:
- `ccxt.OrderNotFound` → `False`
- Permanent codes (Binance `-2011`, `-2013`, Bybit `110001`, `170213` и др.) → `False`
- Retryable → re-raise после backoff

**Вывод:** `_cancel_confirmed` не может проверять коды напрямую. И `True`, и `False` означают «ордера на бирже нет» — оба = успех. Только exception = «не подтверждено». Это упрощает логику по сравнению с legacy `orderRemove.function.php`, где коды проверялись явно.

## 3. Реальные коды бирж (ORDER_GONE_CODES)

Из CcxtExecutor видны permanent-коды, при которых `cancel_order` возвращает `False`:

**Binance:**
- `-2011` — CANCEL_REJECTED / Unknown order
- `-2013` — Order does not exist

**Bybit:**
- `110001` — Order does not exist
- `170213` — Order does not exist

Эти коды **обрабатываются внутри executor**, reconciler их не видит. Для reconciler результат `False` от `cancel_order` достаточен.

## 4. Замеченное, но не тронутое в engine.py

1. **`shift_grid()` — cancel без проверки (строки 369-372):**
   ```python
   await self.executor.cancel_order(order.exchange_order_id)
   order.status = OrderStatus.CANCELLED  # Безусловно!
   ```
   Если `cancel_order` вернёт `False` (ордер уже исполнен) или кинет exception, статус всё равно станет CANCELLED. Ордер жив на бирже → orphan. **Reconciler теперь ловит это.**

2. **`_flip_order()` → `None` (строки 326-328):**
   Если `place_order` не прошёл — `None`. Вызывающий код делает `if new_order is not None: append` — иначе уровень потерян навсегда. **Reconciler логирует потерянные уровни, но восстановление требует знания стратегии.**

3. **`on_order_filled()` — append вместо замены (строки 192, 227, etc.):**
   Каждый fill добавляет новый ордер через `append`, FILLED ордер остаётся в списке. За месяц state.orders вырастает до ~12000 записей. **Reconciler чистит bloat.**

4. **`tick()` — потенциальный race с WS (строки 492-502):**
   `engine.tick()` и `process_ws_fill()` оба обрабатывают fills. Lock в `tick_grid()` защищает от одновременного исполнения, но если WS-fill пришёл между `get_open_orders()` и `get_order_status()`, может быть дубль. Существующий код уже обрабатывает это (проверка `order.status == PLACED` в `process_ws_fill`).

5. **`_handle_buy_filled()` — пересчёт лота через `order.amount` (строка 190):**
   Simple strategy: `_flip_order(order, SELL, order.price_sell, order.amount)` — использует `amount` из исходного ордера. Если биржа частично исполнила ордер, `amount` не обновляется. Известный баг, но он **не входит в эту задачу**.

## 5. Чего Reconciler не покрывает

1. **Восстановление потерянных уровней** — только детекция. Для восстановления нужно знать, какой ордер ставить (side, price, amount), а это решение стратегии.

2. **Частичное исполнение (partial fills)** — executor не возвращает `filled_amount`, reconciler не проверяет это.

3. **Двойная экспозиция при shift** — reconciler отменяет orphan, но не проверяет, что shift уже поставил новый ордер на ту же цену. Возможно временное окно с двумя ордерами на одном уровне.

4. **Мульти-символ** — reconciler привязан к одному символу через executor. Если executor вдруг вернёт ордера другого символа, reconciler их отменит как orphans. На практике executor фильтрует по символу внутри.

5. **DB-стейт cleanup** — reconciler чистит `state.orders` в памяти. Записи в таблице `grid_orders` остаются (FILLED/CANCELLED). Очистка БД — отдельная задача.

## 6. Риски интеграции

1. **Дополнительные API-запросы:** Reconciler не делает свой `get_open_orders()` — он **переиспользует** тот же state, который уже обновлён `engine.tick()`. Но `enforce()` делает собственный `get_open_orders()` (один запрос) + `get_order_status()` для каждого ghost + `cancel_order()` для orphans/stale_cancels. При 30-секундном интервале это приемлемо (~2-5 запросов на цикл).

2. **Rate limits:** Каждый запрос в reconciler проходит через `asyncio.sleep(0.15)` — тот же паттерн, что в engine.py. При 5 ghosts + 2 orphans: ~1 секунда дополнительно на цикл.

3. **Двойное обнаружение ghosts:** `engine.tick()` УЖЕ находит пропавшие PLACED-ордера и обрабатывает их. Reconciler запускается ПОСЛЕ tick, поэтому видит только оставшиеся. Потенциальный дубль: если tick пометил ордер как FILLED но ещё не вызвал `on_order_filled` до reconciler... Нет, это невозможно — tick синхронный, reconciler запускается после его завершения.

4. **Bloat cleanup и persist:** Reconciler удаляет не-PLACED из `state.orders`. `_persist_state()` вызывается ПОСЛЕ reconciler — она увидит уже очищенный state. Ордера с `exchange_order_id`, которых нет в state, помечаются `CANCELLED` в БД (строка 92 в `_persist_state`). Это корректно.

5. **dry_run по умолчанию:** Reconciler запускается в `dry_run=True` (env `GRID_RECONCILER_MODE=dry_run`). Это означает: находит и логирует проблемы, но ничего не чинит. Для включения: `GRID_RECONCILER_MODE=active`.
