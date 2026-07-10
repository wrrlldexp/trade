import asyncio
from app.db import AsyncSessionLocal
from sqlalchemy import text

GID = "50a2417d-3538-4774-9a32-2c5b9cab457d"

async def stats():
    async with AsyncSessionLocal() as s:
        # Sample payload to understand structure
        r = await s.execute(text("SELECT payload, price, amount, event_type, pnl_delta FROM trade_events WHERE grid_id=:gid LIMIT 5"), {"gid": GID})
        rows = r.fetchall()
        print("=== SAMPLE TRADE EVENTS ===")
        for row in rows:
            print(f"event_type={row[3]}, price={row[1]}, amount={row[2]}, pnl_delta={row[4]}, payload={row[0]}")
        print()

        # By event_type
        r2 = await s.execute(text("SELECT event_type, COUNT(*), COALESCE(SUM(CAST(pnl_delta AS NUMERIC)),0) FROM trade_events WHERE grid_id=:gid GROUP BY event_type"), {"gid": GID})
        evts = r2.fetchall()
        print("=== ПО EVENT_TYPE ===")
        for e in evts:
            print(f"{e[0]}: кол-во={e[1]}, PnL={float(e[2]):.6f}")
        print()

        # Grid orders — all details
        r3 = await s.execute(text("SELECT status, COUNT(*), COALESCE(SUM(count_complete),0), COALESCE(SUM(CAST(profit AS NUMERIC)),0) FROM grid_orders WHERE grid_id=:gid GROUP BY status"), {"gid": GID})
        orders = r3.fetchall()
        print("=== ОРДЕРЫ ===")
        total_cycles = 0; total_profit = 0
        for o in orders:
            cy = int(o[2]); pr = float(o[3])
            total_cycles += cy; total_profit += pr
            print(f"{o[0]}: кол-во={o[1]}, циклов={cy}, прибыль=${pr:.6f}")
        print(f"Всего циклов: {total_cycles}, прибыль с ордеров: ${total_profit:.6f}")
        print()

        # Grid orders — check columns
        r4 = await s.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='grid_orders' ORDER BY ordinal_position"))
        cols = [row[0] for row in r4.fetchall()]
        print(f"grid_orders columns: {cols}")
        print()

        # Sample orders
        r5 = await s.execute(text("SELECT price, price_sell, amount, profit, count_complete, side, status FROM grid_orders WHERE grid_id=:gid LIMIT 5"), {"gid": GID})
        for row in r5.fetchall():
            print(f"buy@{row[0]} sell@{row[1]} amt={row[2]} profit={row[3]} cycles={row[4]} side={row[5]} status={row[6]}")
        print()

        # Volume from grid_orders (buy*amount + sell*amount per cycle)
        r6 = await s.execute(text("SELECT COALESCE(SUM((CAST(price AS NUMERIC) + CAST(price_sell AS NUMERIC)) * CAST(amount AS NUMERIC) * count_complete), 0) FROM grid_orders WHERE grid_id=:gid"), {"gid": GID})
        vol = float(r6.scalar())
        print(f"Примерный торговый объём (из ордеров): ${vol:.4f}")

        # Deposit info
        r7 = await s.execute(text("SELECT lot_quote, levels_above, levels_below, realized_pnl, total_trades FROM grids WHERE id=:gid"), {"gid": GID})
        gi = r7.fetchone()
        lot = float(gi[0]) if gi[0] else 0
        levels = int(gi[1]) + int(gi[2])
        deposit = lot * levels
        pnl = float(gi[3])
        print(f"Лот: ${lot}, уровней: {levels}, депозит в работе: ~${deposit:.2f}")
        print(f"Realized PnL: ${pnl:.6f}")
        if deposit > 0:
            print(f"ROI на депозит: {(pnl/deposit)*100:.2f}%")

asyncio.run(stats())
