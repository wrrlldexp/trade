"""Exchange accounts API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.crypto import encrypt
from app.core.deps import require_role
from app.db import get_db
from app.models import ExchangeAccount, GridStatus, User, UserRole
from app.schemas.account import (
    ExchangeAccountCreate,
    ExchangeAccountResponse,
    ExchangeAccountTestResponse,
    ExchangeAccountUpdate,
)


class ConvertRequest(BaseModel):
    from_currency: str = Field(..., description="Валюта из которой конвертируем")
    to_currency: str = Field(..., description="Валюта в которую конвертируем")
    amount: float = Field(..., gt=0, description="Количество from_currency для конвертации")

router = APIRouter()


@router.get("/", response_model=list[ExchangeAccountResponse])
async def list_accounts(
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[ExchangeAccountResponse]:
    query = select(ExchangeAccount)
    if current_user.role == UserRole.ADMIN:
        query = query.where(ExchangeAccount.owner_id == current_user.id)
    result = await db.execute(query)
    return [ExchangeAccountResponse.model_validate(item) for item in result.scalars().all()]


@router.get("/balances", response_model=list[dict])
async def get_balances(
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Получить балансы всех активных аккаунтов."""
    query = select(ExchangeAccount).where(ExchangeAccount.is_active.is_(True))
    if current_user.role == UserRole.ADMIN:
        query = query.where(ExchangeAccount.owner_id == current_user.id)
    result = await db.execute(query)
    accounts = result.scalars().all()

    balances = []
    for account in accounts:
        try:
            executor = account.to_executor(paper_mode=False)
            raw = await executor.exchange.fetch_balance()
            close = getattr(executor, "close", None)
            if callable(close):
                await close()
            free = raw.get("free", {})
            total = raw.get("total", {})
            used = raw.get("used", {})
            # Собираем все валюты с ненулевым балансом
            currencies: list[dict] = []
            for currency in sorted(total.keys()):
                t = float(total.get(currency, 0) or 0)
                if t > 0:
                    f = float(free.get(currency, 0) or 0)
                    u = float(used.get(currency, 0) or 0)
                    currencies.append({
                        "currency": currency,
                        "total": str(t),
                        "free": str(f),
                        "used": str(u),
                    })
            balances.append({
                "account_id": str(account.id),
                "name": account.name,
                "exchange": account.exchange,
                "testnet": account.is_testnet,
                "currencies": currencies,
            })
        except Exception:
            balances.append({
                "account_id": str(account.id),
                "name": account.name,
                "exchange": account.exchange,
                "testnet": account.is_testnet,
                "currencies": [],
                "error": "Не удалось получить баланс",
            })
    return balances


@router.post("/", response_model=ExchangeAccountResponse)
async def create_account(
    payload: ExchangeAccountCreate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ExchangeAccountResponse:
    account = ExchangeAccount(
        owner_id=current_user.id,
        name=payload.name,
        exchange=payload.exchange,
        api_key_enc=encrypt(payload.api_key),
        api_secret_enc=encrypt(payload.api_secret),
        is_testnet=payload.is_testnet,
    )
    db.add(account)
    await db.flush()
    await log_action(db, current_user.id, "account.create", entity_type="exchange_account", entity_id=str(account.id), request=request)
    return ExchangeAccountResponse.model_validate(account)


@router.patch("/{account_id}", response_model=ExchangeAccountResponse)
async def update_account(
    account_id: UUID,
    payload: ExchangeAccountUpdate,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ExchangeAccountResponse:
    result = await db.execute(select(ExchangeAccount).where(ExchangeAccount.id == account_id, ExchangeAccount.owner_id == current_user.id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    data = payload.model_dump(exclude_none=True)
    if "api_key" in data:
        account.api_key_enc = encrypt(data.pop("api_key"))
    if "api_secret" in data:
        account.api_secret_enc = encrypt(data.pop("api_secret"))
    for field, value in data.items():
        setattr(account, field, value)
    await log_action(db, current_user.id, "account.update", entity_type="exchange_account", entity_id=str(account.id), request=request)
    return ExchangeAccountResponse.model_validate(account)


@router.delete("/{account_id}")
async def delete_account(
    account_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(ExchangeAccount)
        .where(ExchangeAccount.id == account_id, ExchangeAccount.owner_id == current_user.id)
        .options(selectinload(ExchangeAccount.grids))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    # H-6: запрет удаления аккаунта с работающими сетками
    if any(g.status == GridStatus.RUNNING for g in account.grids):
        raise HTTPException(status_code=409, detail="Нельзя удалить аккаунт с активными сетками. Сначала остановите все сетки.")
    await db.delete(account)
    await log_action(db, current_user.id, "account.delete", entity_type="exchange_account", entity_id=str(account.id), request=request)
    return {"success": True}


@router.post("/{account_id}/test", response_model=ExchangeAccountTestResponse)
async def test_account(
    account_id: UUID,
    current_user: User = Depends(require_role(UserRole.VIEWER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ExchangeAccountTestResponse:
    query = select(ExchangeAccount).where(ExchangeAccount.id == account_id)
    if current_user.role == UserRole.ADMIN:
        query = query.where(ExchangeAccount.owner_id == current_user.id)

    result = await db.execute(query)
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        executor = account.to_executor(paper_mode=False)
        balance = await executor.get_balance()
        close = getattr(executor, "close", None)
        if callable(close):
            await close()
        return ExchangeAccountTestResponse(
            success=True,
            message="Connection is healthy",
            balance={"base": str(balance.base), "quote": str(balance.quote)},
            exchange=account.exchange,
            testnet=account.is_testnet,
        )
    except Exception as exc:
        # C-3: не прокидываем str(exc) клиенту — может содержать API-ключи
        import logging
        logging.getLogger("app.accounts").exception("Account test failed for %s", account_id)
        error_type = type(exc).__name__
        return ExchangeAccountTestResponse(
            success=False,
            message="Connection test failed",
            balance=None,
            exchange=account.exchange,
            testnet=account.is_testnet,
            error=f"Ошибка подключения: {error_type}",
        )


@router.get("/{account_id}/markets")
async def get_markets(
    account_id: UUID,
    search: str = "",
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Получить список доступных торговых пар для конвертации."""
    query = select(ExchangeAccount).where(ExchangeAccount.id == account_id)
    if current_user.role == UserRole.ADMIN:
        query = query.where(ExchangeAccount.owner_id == current_user.id)
    result = await db.execute(query)
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    executor = account.to_executor(paper_mode=False)
    try:
        await executor.exchange.load_markets()
        markets = []
        search_upper = search.upper()
        for symbol, market in executor.exchange.markets.items():
            if market.get("type") != "spot" or not market.get("active"):
                continue
            if search_upper and search_upper not in symbol.upper():
                continue
            markets.append({
                "symbol": symbol,
                "base": market.get("base", ""),
                "quote": market.get("quote", ""),
            })
        markets.sort(key=lambda m: m["symbol"])
        return markets
    finally:
        await executor.close()


@router.post("/{account_id}/convert")
async def convert_currency(
    account_id: UUID,
    payload: ConvertRequest,
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Конвертировать валюту через маркет-ордер на бирже."""
    query = select(ExchangeAccount).where(ExchangeAccount.id == account_id)
    if current_user.role == UserRole.ADMIN:
        query = query.where(ExchangeAccount.owner_id == current_user.id)
    result = await db.execute(query)
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    executor = account.to_executor(paper_mode=False)
    try:
        await executor.exchange.load_markets()

        from_c = payload.from_currency.upper()
        to_c = payload.to_currency.upper()
        amount = payload.amount

        # Определяем направление: прямая пара (FROM/TO) или обратная (TO/FROM)
        direct_symbol = f"{from_c}/{to_c}"
        reverse_symbol = f"{to_c}/{from_c}"

        if direct_symbol in executor.exchange.markets:
            # Продаём from_currency → получаем to_currency
            order = await executor.exchange.create_market_order(direct_symbol, "sell", amount)
        elif reverse_symbol in executor.exchange.markets:
            # Покупаем to_currency за from_currency
            # Нужно пересчитать amount: сколько to_currency купить
            ticker = await executor.exchange.fetch_ticker(reverse_symbol)
            price = ticker.get("last") or ticker.get("ask") or 0
            if not price:
                raise HTTPException(status_code=400, detail="Не удалось получить цену")
            buy_amount = amount / price
            order = await executor.exchange.create_market_order(reverse_symbol, "buy", buy_amount)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Нет торговой пары для {from_c} → {to_c}. Попробуйте конвертировать через USDT.",
            )

        await log_action(
            db, current_user.id, "account.convert",
            entity_type="exchange_account", entity_id=str(account.id),
            request=request,
            payload={"amount": amount, "from": from_c, "to": to_c},
        )

        filled = order.get("filled", 0)
        cost = order.get("cost", 0)
        avg_price = order.get("average", order.get("price", 0))

        return {
            "success": True,
            "order_id": str(order.get("id", "")),
            "filled": filled,
            "cost": cost,
            "average_price": avg_price,
            "from_currency": from_c,
            "to_currency": to_c,
        }
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.getLogger("app.accounts").exception("Convert failed for %s", account_id)
        raise HTTPException(status_code=400, detail=f"Ошибка конвертации: {type(exc).__name__}") from exc
    finally:
        await executor.close()
