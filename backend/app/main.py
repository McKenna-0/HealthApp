from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from .config import settings
from .db import init_db

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from .db import SessionLocal
    from .services.muscles import backfill_exercise_muscles
    from .services.strength import seed_exercises

    with SessionLocal() as db:
        seed_exercises(db)
        backfill_exercise_muscles(db)
    from .scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Health App", lifespan=lifespan)

# Dev convenience: Vite dev server proxies /api, but allow direct calls too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "data_source": settings.data_source, "tz": settings.tz}


from .routers import (  # noqa: E402
    ai,
    analytics,
    bloodwork,
    checkin,
    context,
    exercises,
    food,
    metrics,
    mfp,
    routines,
    settings as settings_router,
    sync,
    weight,
    workouts,
)

app.include_router(sync.router)
app.include_router(metrics.router)
app.include_router(weight.router)
app.include_router(food.router)
app.include_router(context.router)
app.include_router(checkin.router)
app.include_router(analytics.router)
app.include_router(settings_router.router)
app.include_router(workouts.router)
app.include_router(exercises.router)
app.include_router(routines.router)
app.include_router(bloodwork.router)
app.include_router(ai.router)
app.include_router(mfp.router)

# Serve built frontend (SPA) if present.
if STATIC_DIR.is_dir() and (STATIC_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = STATIC_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
