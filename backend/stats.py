import asyncio
from app.config import Settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

s = Settings()

async def main():
    engine = create_async_engine(s.DATABASE_URL)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT name, symbol, strategy, mode, status, total_trades, realized_pnl, lot_quote, grid_step, created_at FROM grids ORDER BY created_at"))
        print("=== GRIDS ===")
        for row in r.fetchall(): print(dict(row._mapping))

        r = await conn.execute(text("SELECT COUNT(*) FROM trade_events"))
        print(f"\nTRADE_EVENTS: {r.scalar()}")

        r = await conn.execute(text("""
            SELECT grid_id, COUNT(*) as cnt,
                   SUM(CASE WHEN status='filled' THEN 1 ELSE 0 END) as filled,
                   SUM(profit) as total_profit
            FROM grid_orders GROUP BY grid_id
        """))
        print("\n=== ORDERS BY GRID ===")
        for row in r.fetchall(): print(dict(row._mapping))

        r = await conn.execute(text("""
            SELECT DATE(filled_at) as day, COUNT(*) as trades, SUM(profit) as pnl
            FROM grid_orders WHERE status='filled' AND filled_at IS NOT NULL
            GROUP BY DATE(filled_at) ORDER BY day
        """))
        print("\n=== DAILY PNL ===")
        for row in r.fetchall(): print(dict(row._mapping))

        r = await conn.execute(text("""
            SELECT
              COUNT(CASE WHEN profit > 0 THEN 1 END) as wins,
              COUNT(CASE WHEN profit < 0 THEN 1 END) as losses,
              COUNT(CASE WHEN profit = 0 THEN 1 END) as neutral,
              MAX(profit) as best,
              MIN(CASE WHEN profit < 0 THEN profit END) as worst,
              AVG(CASE WHEN profit != 0 THEN profit END) as avg
            FROM grid_orders WHERE status='filled'
        """))
        print("\n=== WIN/LOSS ===")
        for row in r.fetchall(): print(dict(row._mapping))

        r = await conn.execute(text("SELECT MIN(filled_at) as first_trade, MAX(filled_at) as last_trade FROM grid_orders WHERE status='filled'"))
        print("\n=== UPTIME ===")
        for row in r.fetchall(): print(dict(row._mapping))

        r = await conn.execute(text("""
            SELECT g.name, g.symbol, g.strategy, g.mode,
                   COUNT(o.id) as orders,
                   SUM(CASE WHEN o.status='filled' THEN 1 ELSE 0 END) as filled,
                   SUM(CASE WHEN o.profit > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN o.profit < 0 THEN 1 ELSE 0 END) as losses,
                   SUM(o.profit) as pnl,
                   MAX(o.profit) as best,
                   MIN(CASE WHEN o.profit < 0 THEN o.profit END) as worst
            FROM grids g LEFT JOIN grid_orders o ON g.id = o.grid_id
            GROUP BY g.id, g.name, g.symbol, g.strategy, g.mode
        """))
        print("\n=== PER GRID ===")
        for row in r.fetchall(): print(dict(row._mapping))

        r = await conn.execute(text("""
            SELECT
              SUM(CASE WHEN side='sell' AND status='filled' THEN amount * price_sell ELSE 0 END) as sell_volume,
              SUM(CASE WHEN side='buy' AND status='filled' THEN amount * price ELSE 0 END) as buy_volume
            FROM grid_orders
        """))
        print("\n=== VOLUME ===")
        for row in r.fetchall(): print(dict(row._mapping))

        r = await conn.execute(text("""
            SELECT EXTRACT(HOUR FROM filled_at)::int as hour, COUNT(*) as cnt
            FROM grid_orders WHERE status='filled' AND filled_at IS NOT NULL
            GROUP BY hour ORDER BY hour
        """))
        print("\n=== HOURLY ===")
        for row in r.fetchall(): print(dict(row._mapping))

asyncio.run(main())
