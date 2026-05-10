import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.config import (
    FRONTEND_URL, RESOURCES_DIR, OUTPUTS_DIR, TEMP_DIR,
    ADMIN_USERNAME, ADMIN_PASSWORD,
)
from backend.database import init_db
from backend.auth import hash_password
from backend.database import get_db
from backend.routes.auth_routes import router as auth_router
from backend.routes.admin_routes import router as admin_router
from backend.routes.proposals_routes import router as proposals_router

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
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

    # Initialise database tables
    init_db()

    # Seed admin user if not present
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
                (ADMIN_USERNAME, hash_password(ADMIN_PASSWORD)),
            )
            print(f"[startup] Admin user '{ADMIN_USERNAME}' created.")
        else:
            print(f"[startup] Admin user '{ADMIN_USERNAME}' already exists.")

        # Mark any proposals that were left in 'pending' from a previous run as error
        # (they'll never complete since the background task died with the process)
        result = conn.execute(
            """UPDATE proposals SET status='error',
               error_message='Server restarted while generation was in progress. Please try again.'
               WHERE status='pending'"""
        )
        if result.rowcount:
            print(f"[startup] Marked {result.rowcount} stuck pending proposal(s) as error.")


@app.get("/")
def root():
    return {"status": "FMR Automation Platform is running"}


@app.get("/health")
def health():
    return {"status": "ok"}
