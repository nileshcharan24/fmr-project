import logging
import logging.config
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.config import DATABASE_PATH, FRONTEND_URL, RESOURCES_DIR, OUTPUTS_DIR, TEMP_DIR
from backend.database import get_db, init_db
from backend.routes.auth_routes import router as auth_router
from backend.routes.admin_routes import router as admin_router
from backend.routes.proposals_routes import router as proposals_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(title="FMR Automation Platform", version="1.0.0")

log = logging.getLogger("fmr")

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    log.error("422 on %s %s — %s", request.method, request.url.path, errors)
    # Flatten to a single readable string so the frontend can display it
    messages = "; ".join(
        f"{' -> '.join(str(l) for l in e['loc'])}: {e['msg']}"
        for e in errors
    )
    return JSONResponse(status_code=422, content={"detail": messages})

# --- CORS ---
_origins = list({FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"})
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # covers all Vercel preview/prod URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(proposals_router)


@app.on_event("startup")
def startup():
    # Create required directories
    for folder in [RESOURCES_DIR, OUTPUTS_DIR, TEMP_DIR,
                   RESOURCES_DIR / "templates", RESOURCES_DIR / "deliverables",
                   RESOURCES_DIR / "guidelines", RESOURCES_DIR / "clusters"]:
        Path(folder).mkdir(parents=True, exist_ok=True)

    # init_db handles table creation, migrations, and admin seeding in one place
    init_db()

    # Mark proposals stuck in 'pending' (background task died with previous process)
    with get_db() as conn:
        result = conn.execute(
            """UPDATE proposals SET status='error',
               error_message='Server restarted while generation was in progress. Please try again.'
               WHERE status='pending'"""
        )
        if result.rowcount:
            log.info("Marked %d stuck pending proposal(s) as error.", result.rowcount)


@app.get("/")
def root():
    return {"status": "FMR Automation Platform is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug")
def debug():
    """Public diagnostic endpoint — visit Railway-URL/debug to verify the backend."""
    info = {
        "database_path": str(DATABASE_PATH),
        "db_file_exists": Path(DATABASE_PATH).exists(),
        "frontend_url_env": os.getenv("FRONTEND_URL", "(not set)"),
        "admin_username_env": os.getenv("ADMIN_USERNAME", "(not set)"),
        "admin_password_set": bool(os.getenv("ADMIN_PASSWORD")),
    }
    # Check if admin user exists in DB
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, status, role FROM users WHERE username = ?",
                (os.getenv("ADMIN_USERNAME", "admin"),),
            ).fetchone()
            info["admin_in_db"] = dict(row) if row else None
            info["total_users"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    except Exception as e:
        info["db_error"] = str(e)
    return info
