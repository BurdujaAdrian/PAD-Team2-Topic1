import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.warehouse import init_warehouse


logging.basicConfig(
    level=settings().log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("etl")


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Compose starts the ETL only once warehouse-db is healthy, so the tables
    # can be created before the first run.
    init_warehouse()
    logger.info("etl_started interval_seconds=%s", settings().etl_interval_seconds)
    yield
    logger.info("etl_stopped")


app = FastAPI(
    lifespan=lifespan,
    title="ETL Service",
    description="Extracts the service databases, transforms the rows and loads them into the warehouse.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
