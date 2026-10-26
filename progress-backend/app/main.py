import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text, update

from .config import settings
from .db import Base, SessionLocal, engine
from .models import Entry, Status
from .routers import (
    admin,
    adminui,
    auth,
    conversations,
    entries,
    goals,
    progress,
    push,
    reports,
    tasks,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger(__name__)

if settings.sentry_dsn:
    import sentry_sdk

    # FastAPI, Starlette, SQLAlchemy, httpx and logging are picked up automatically.
    # The logging integration matters most here: background jobs catch their own
    # exceptions and log them, so without it a crashed check-in would never reach Sentry.
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # Transcripts are someone's day in their own words. Keep request bodies,
        # cookies and emails out of a third-party service.
        send_default_pii=False,
        max_request_body_size="never",
    )


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

    log.info("stt=%s llm=%s", settings.stt_provider, settings.openai_model)
    from .services.costs import missing_prices

    unpriced = missing_prices()
    if unpriced:
        log.warning(
            "no price set for %s: tokens are counted but cost is recorded as $0",
            ", ".join(unpriced),
        )
    log.info("sentry=%s", "on" if settings.sentry_dsn else "off")

    reminders: asyncio.Task | None = None
    if settings.reminders_enabled and settings.vapid_private_key:
        from .services.reminders import loop as reminder_loop

        reminders = asyncio.create_task(reminder_loop())
        log.info("reminder loop started")
    elif settings.reminders_enabled:
        log.warning("reminders on but VAPID keys missing; nothing will be sent")

    # Not optional like the reminders: the letter to someone who deleted their account
    # promises the data is gone after the grace period, and this is what keeps it.
    from .services.accounts import loop as purge_loop

    purge = asyncio.create_task(purge_loop())

    # Memory: conversations quiet for a while, and each person's day closed at night.
    # Both pick up where a restart left off (memory_extracted_at lives in the database).
    from .services.memory import close_day_loop, memory_loop

    memory_tasks = [asyncio.create_task(memory_loop()), asyncio.create_task(close_day_loop())]

    yield

    for task in (purge, *memory_tasks):
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    if reminders is not None:
        reminders.cancel()
        with suppress(asyncio.CancelledError):
            await reminders

    from .services import llm, stt

    await llm.aclose()
    await stt.aclose()
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
    # The frontend is another origin, and the browser hides any header not listed here.
    # The sign-in screen reads this one to say how long a lockout lasts.
    expose_headers=["Retry-After"],
)

for router in (
    auth.router,
    goals.router,
    entries.router,
    conversations.router,
    progress.router,
    reports.router,
    push.router,
    tasks.router,
    admin.router,
    adminui.router,
):
    app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Alive or not, for anyone. Which providers are configured is admin-only: see
    /api/admin/overview. The reason a check failed goes to the log, not the response."""
    checks = {"api": "ok"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        log.exception("health check: database unreachable")
        checks["database"] = "error"
    return checks
