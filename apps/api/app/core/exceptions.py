from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.core.request_context import normalize_request_id
from app.core.schemas import ProblemDetails


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", normalize_request_id(None))


def _problem_response(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
) -> JSONResponse:
    request_id = _request_id(request)
    payload = ProblemDetails(
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status,
        content=payload.model_dump(),
        media_type="application/problem+json",
        headers={"X-Request-ID": request_id},
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        title = (
            HTTPStatus(exc.status_code).phrase
            if exc.status_code in HTTPStatus._value2member_map_
            else "Erro"
        )
        return _problem_response(
            request,
            status=exc.status_code,
            title=title,
            detail=str(exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del exc
        return _problem_response(
            request,
            status=422,
            title="Dados inválidos",
            detail="Revise os campos enviados e tente novamente.",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        get_logger(component="exception").error(
            "unhandled_exception",
            error_type=type(exc).__name__,
            path=request.url.path,
        )
        return _problem_response(
            request,
            status=500,
            title="Erro interno",
            detail="Não foi possível concluir a solicitação.",
        )
