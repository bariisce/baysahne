"""Consistent error envelope: {"error": {"code": str, "message": str (Turkish, user-facing), "details": any}}.

Internal exception details are logged server-side and never returned to clients.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.db import unavailable_hint

log = logging.getLogger("baysahne.errors")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def not_found(message: str = "Kayıt bulunamadı.") -> AppError:
    return AppError(404, "not_found", message)


def conflict(code: str, message: str, details=None) -> AppError:
    return AppError(409, code, message, details)


def bad_request(code: str, message: str, details=None) -> AppError:
    return AppError(400, code, message, details)


def forbidden(message: str = "Bu işlem için yetkiniz yok.") -> AppError:
    return AppError(403, "forbidden", message)


def _body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


_HTTP_MESSAGES = {
    401: ("unauthorized", "Oturum açmanız gerekiyor."),
    403: ("forbidden", "Bu işlem için yetkiniz yok."),
    404: ("not_found", "İstenen kaynak bulunamadı."),
    405: ("method_not_allowed", "Bu işlem desteklenmiyor."),
    413: ("payload_too_large", "Gönderilen dosya çok büyük."),
    429: ("rate_limited", "Çok fazla deneme yapıldı. Lütfen biraz sonra tekrar deneyin."),
}

_FIELD_MESSAGES = {
    "missing": "Bu alan zorunludur.",
    "string_too_short": "Bu alan çok kısa.",
    "string_too_long": "Bu alan çok uzun.",
    "value_error": "Geçersiz değer.",
    "int_parsing": "Sayı olmalıdır.",
    "datetime_parsing": "Geçerli bir tarih ve saat girin.",
    "datetime_from_date_parsing": "Geçerli bir tarih ve saat girin.",
    "uuid_parsing": "Geçersiz kimlik.",
    "enum": "İzin verilen değerlerden biri olmalıdır.",
    "literal_error": "İzin verilen değerlerden biri olmalıdır.",
    "url_parsing": "Geçerli bir bağlantı (URL) girin.",
    "url_scheme": "Bağlantı https:// ile başlamalıdır.",
    "greater_than_equal": "Değer çok küçük.",
    "less_than_equal": "Değer çok büyük.",
    "too_long": "Çok fazla öğe var.",
}


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
            msg = err.get("msg", "")
            # Custom validators raise ValueError with a Turkish message; pydantic prefixes "Value error, ".
            if err.get("type") == "value_error" and msg.startswith("Value error, "):
                text = msg.removeprefix("Value error, ")
            else:
                text = _FIELD_MESSAGES.get(err.get("type", ""), "Geçersiz değer.")
            fields.append({"field": ".".join(loc), "message": text})
        return JSONResponse(
            _body("validation_error", "Lütfen formdaki hataları düzeltin.", {"fields": fields}),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code, message = _HTTP_MESSAGES.get(exc.status_code, ("http_error", "İstek işlenemedi."))
        return JSONResponse(_body(code, message), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(OperationalError)
    @app.exception_handler(PoolTimeoutError)
    async def _database_unavailable(request: Request, exc: Exception):
        # Database down, unreachable or saturated: a retryable condition, not a bug — no stack trace.
        log.warning("Database unavailable on %s %s: %s. %s", request.method, request.url.path,
                    type(exc).__name__, unavailable_hint())
        return JSONResponse(
            _body("service_unavailable", "Hizmet geçici olarak kullanılamıyor. Lütfen biraz sonra tekrar deneyin."),
            status_code=503,
            headers={"Retry-After": "10"},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            _body("internal_error", "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin."), status_code=500
        )
