import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.pipeline import run_all
from app.warehouse import init_warehouse

logging.basicConfig(
    level=settings().log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("etl")


async def run_periodically() -> None:
    while True:
        # The ETL is blocking code (psycopg, httpx); on a thread it leaves the
        # event loop free, so /health keeps answering during a run.
        await asyncio.to_thread(run_all)
        await asyncio.sleep(settings().etl_interval_seconds)


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Compose starts the ETL only once warehouse-db is healthy, so the tables
    # can be created before the first run.
    init_warehouse()
    logger.info("etl_started interval_seconds=%s", settings().etl_interval_seconds)
    task = asyncio.create_task(run_periodically())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    logger.info("etl_stopped")


app = FastAPI(
    lifespan=lifespan,
    title="ETL Service",
    description=(
        "Extracts the service databases, transforms the rows and loads them into the warehouse."
    ),
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
async def run() -> dict[str, list[dict]]:
    return {"results": await asyncio.to_thread(run_all)}
