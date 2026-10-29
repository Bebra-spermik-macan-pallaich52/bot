import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.db import init_db, close_db
from app.api.v1.role_api_router import router as role_router
from app.api.v1.profile_api_router import router as profile_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def on_startup(app: FastAPI):
    init_db()
    try:
        yield
    finally:
        close_db()


# Lifespan смонтированного приложения автоматически не запускается:
# основной сервер управляет БД; app_v1 поддерживает и отдельный запуск.
main_app = FastAPI(lifespan=on_startup, docs_url=None, redoc_url=None, openapi_url=None)
app_v1 = FastAPI(title="API v1", version="1.0.0", lifespan=on_startup)
app_v1.include_router(role_router)
app_v1.include_router(profile_router)
main_app.mount("/api/v1", app_v1)


@app_v1.exception_handler(ValueError)
async def duplicate_error(request: Request, exc: ValueError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app_v1.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=400, content={"detail": "Нарушение целостности данных"})


@app_v1.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logger.error("Ошибка базы данных: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:main_app", host="127.0.0.1", port=8000)
