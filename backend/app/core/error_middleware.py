"""Middleware для перехвата необработанных исключений и записи в BotLog."""

from __future__ import annotations

import traceback as tb_module

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core import bot_logger
from app.models.enums import LogLevel

# M-3: пути, для которых str(exc) может содержать чувствительные данные
_SENSITIVE_PATHS = {"/api/auth/login", "/api/auth/login/2fa", "/api/auth/password", "/api/auth/invites/accept"}


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            source = "unknown"
            if exc.__traceback__:
                tb_entries = tb_module.extract_tb(exc.__traceback__)
                for frame in reversed(tb_entries):
                    if "app/" in frame.filename or "worker/" in frame.filename:
                        idx = frame.filename.find("app/")
                        if idx == -1:
                            idx = frame.filename.find("worker/")
                        if idx != -1:
                            source = f"{frame.filename[idx:]}:{frame.lineno}:{frame.name}"
                            break

            # M-3: маскируем сообщение об ошибке для auth-путей
            path = str(request.url.path)
            if path in _SENSITIVE_PATHS:
                error_msg = f"Необработанная ошибка: {type(exc).__name__} (детали скрыты — чувствительный путь)"
            else:
                error_msg = f"Необработанная ошибка: {type(exc).__name__}: {exc}"

            # ErrorDiagnostor: автоматическая диагностика ошибки
            from app.core.log_translator import diagnose_error

            traceback_text = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__)) if exc.__traceback__ else str(exc)
            diagnosis = diagnose_error(error_msg, traceback=traceback_text, source=source)

            await bot_logger.log(
                LogLevel.ERROR,
                error_msg,
                payload={
                    "path": path,
                    "method": request.method,
                    "error_source": source,
                    "diagnosis": {
                        "title": diagnosis.title,
                        "cause": diagnosis.cause,
                        "fix": diagnosis.fix,
                        "doc_ref": diagnosis.doc_ref,
                    },
                },
                exc=exc,
                stack_depth=2,
            )

            return JSONResponse(
                status_code=500,
                content={"detail": "Внутренняя ошибка сервера"},
            )
