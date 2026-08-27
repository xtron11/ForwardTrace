import asyncio
import asyncio
import logging
from contextlib import asynccontextmanager, suppress, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text, update

from .config import settings
from .db import Base, SessionLocal, engine
from .models import Entry, Status
from .routers import admin, auth, entries, goals, push, reports, tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger(__name__)


async def _check_schema() -> None:
    """Fail loudly at startup instead of at the first insert.

    A missing column surfaces as a 500 on whatever endpoint happens to touch it, with a
    200-line traceback. Checking here turns that into one readable line.
    """
    from sqlalchemy import inspect

    async with engine.connect() as conn:
        try:
            present = await conn.run_sync(
                lambda sync_conn: {
                    table: {c["name"] for c in inspect(sync_conn).get_columns(table)}
                    for table in inspect(sync_conn).get_table_names()
                }
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Cannot read the database schema: {exc}") from exc

    missing: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in present:
            missing.append(f"table {table.name}")
            continue
        for column in table.columns:
            if column.name not in present[table.name]:
                missing.append(f"{table.name}.{column.name}")

    if missing:
        raise RuntimeError(
            "Database schema is out of date - missing: "
            + ", ".join(missing[:10])
            + (" …" if len(missing) > 10 else "")
            + ". Run: alembic upgrade head"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.audio_dir).mkdir(parents=True, exist_ok=True)
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.warning("created tables from models; prefer 'alembic upgrade head'")
    else:
        await _check_schema()

    # Background tasks live in this process. A restart mid-task (a --reload, a deploy,
    # a crash) strands the entry in "processing" forever. Mark those failed on boot so
    # the user gets a Retry button instead of a spinner that never resolves.
    async with SessionLocal() as db:
        result = await db.execute(
            update(Entry)
            .where(Entry.status.in_([Status.processing.value, Status.pending.value]))
            .values(
                status=Status.failed.value,
                error="Interrupted by a server restart. Retry to process it.",
            )
        )
        await db.commit()
        if result.rowcount:
            log.warning("reset %s interrupted entries to failed", result.rowcount)

    log.info("stt=%s llm=%s", settings.stt_provider, settings.llm_provider)

    reminders: asyncio.Task | None = None
    if settings.reminders_enabled and settings.vapid_private_key:
        from .services.reminders import loop as reminder_loop

        reminders = asyncio.create_task(reminder_loop())
        log.info("reminder loop started")
    elif settings.reminders_enabled:
        log.warning("reminders on but VAPID keys missing; nothing will be sent")

    yield

    if reminders is not None:
        reminders.cancel()
        with suppress(asyncio.CancelledError):
            await reminders
    await engine.dispose()


app = FastAPI(
    title="Progress API",
    version="0.1.0",
    description="Minimal input, verified extraction, weekly evidence of progress.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    goals.router,
    entries.router,
    reports.router,
    push.router,
    tasks.router,
    admin.router,
):
    app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["meta"])
async def health() -> dict:
    checks = {"api": "ok"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
    checks["stt_provider"] = settings.stt_provider
    checks["llm_provider"] = settings.llm_provider
    return checks
