from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.database import init_db, close_db
from app.routes import client_router, tarif_router


@asynccontextmanager
async def lifespan(app):
    init_db()
    try:
        yield
    finally:
        close_db()


main_app = FastAPI(title="Клиенты и тарифы", version="1.0", lifespan=lifespan,
                   docs_url="/api/v1/docs", redoc_url=None, openapi_url="/api/v1/openapi.json")
main_app.include_router(tarif_router, prefix="/api/v1")
main_app.include_router(client_router, prefix="/api/v1")


@main_app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logging.error("Database error: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Ошибка базы данных"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:main_app", host="127.0.0.1", port=8000)
