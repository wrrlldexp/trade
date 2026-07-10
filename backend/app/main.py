"""FastAPI приложение MoneyBot v2."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, audit, auth, bot, dashboard, grids, logs, market, trades, users, ws
from app.config import get_settings
from app.core.error_middleware import ErrorLoggingMiddleware
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup и shutdown хуки."""
    log.info("backend.starting", environment=settings.ENVIRONMENT)
    yield
    log.info("backend.shutting_down")


app = FastAPI(
    title="MoneyBot v2",
    description="Crypto grid trading bot API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(ErrorLoggingMiddleware)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """Healthcheck для Docker и мониторинга."""
    return {
        "status": "ok",
        "service": "moneybot-backend",
        "version": "2.0.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["system"])
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": "MoneyBot v2",
        "docs": "/docs",
        "health": "/health",
    }


app.include_router(bot.router, prefix="/api/bot", tags=["bot"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(grids.router, prefix="/api/grids", tags=["grids"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
app.include_router(market.router)
app.include_router(ws.router, prefix="/ws", tags=["ws"])
