import logging
import os
import sqlite3
from contextlib import contextmanager

from backend.config import ADMIN_PASSWORD, ADMIN_USERNAME, DATABASE_PATH, OUTPUTS_DIR, TEMP_DIR

log = logging.getLogger(__name__)


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn):
    """ALTER TABLE migrations — only called after all CREATE TABLE statements have run."""
    # Note: DROP TABLE IF EXISTS draft_sessions was removed — it was destroying
    # the table on every startup, causing 'no such table' errors at generation time.

    try:
        conn.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
    except Exception:
        pass  # column already exists

    for col, definition in [
        ("job_id",               "TEXT"),
        ("folder_name",          "TEXT DEFAULT ''"),
        ("cover_letter",         "TEXT DEFAULT ''"),
        ("fest_deliverables",    "TEXT DEFAULT ''"),
        ("company_deliverables", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE proposals ADD COLUMN {col} {definition}")
        except Exception:
            pass  # column already exists


def init_db():
    # ── 0. Ensure directories exist ───────────────────────────────────────────
    os.makedirs(str(DATABASE_PATH.parent), exist_ok=True)
    os.makedirs(str(OUTPUTS_DIR), exist_ok=True)
    os.makedirs(str(TEMP_DIR), exist_ok=True)

    log.info("DATABASE_PATH = %s", DATABASE_PATH)
    log.info("ADMIN_USERNAME from env = %s", os.getenv("ADMIN_USERNAME", "(not set, using default)"))

    conn = get_connection()
    try:
        # ── 1. Create all tables ──────────────────────────────────────────────
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                role          TEXT    NOT NULL DEFAULT 'user',
                status        TEXT    NOT NULL DEFAULT 'active',
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS proposals (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                company_name  TEXT    NOT NULL,
                tier          INTEGER NOT NULL,
                clusters      TEXT    NOT NULL,
                output_folder TEXT    NOT NULL DEFAULT '',
                status        TEXT    DEFAULT 'pending',
                error_message TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                week_string TEXT    NOT NULL,
                count       INTEGER DEFAULT 0,
                UNIQUE(user_id, week_string),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id     INTEGER PRIMARY KEY,
                full_name   TEXT    DEFAULT '',
                designation TEXT    DEFAULT '',
                phone       TEXT    DEFAULT '',
                email       TEXT    DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS draft_sessions (
                id                      TEXT    PRIMARY KEY,
                user_id                 INTEGER NOT NULL,
                company_name            TEXT    NOT NULL,
                tier                    INTEGER NOT NULL,
                clusters                TEXT    NOT NULL,
                banner_count            INTEGER NOT NULL,
                logo_path               TEXT    DEFAULT '',
                manager_name            TEXT    DEFAULT '',
                manager_designation     TEXT    DEFAULT '',
                manager_phone           TEXT    DEFAULT '',
                manager_email           TEXT    DEFAULT '',
                outreach_city           TEXT    DEFAULT 'Bangalore',
                include_csr             INTEGER DEFAULT 0,
                extra_context           TEXT    DEFAULT '',
                llm_questions           TEXT    DEFAULT '',
                fest_deliverables       TEXT    DEFAULT '',
                company_deliverables    TEXT    DEFAULT '',
                brand_event_description TEXT    DEFAULT '',
                portfolio_name          TEXT    DEFAULT '',
                created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)
        conn.commit()
        log.info("Tables created/verified.")

        # ── 2. Migrations ─────────────────────────────────────────────────────
        _migrate(conn)
        conn.commit()
        log.info("Migrations applied.")

        # ── 3. Seed admin — always sync hash from env so password is always current
        from backend.auth import hash_password  # local import avoids circular deps at module level
        new_hash = hash_password(ADMIN_PASSWORD)
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO users (username, password_hash, role, status)
                   VALUES (?, ?, 'admin', 'active')""",
                (ADMIN_USERNAME, new_hash),
            )
            conn.commit()
            log.info("Admin user '%s' created successfully.", ADMIN_USERNAME)
        else:
            conn.execute(
                "UPDATE users SET password_hash=?, role='admin', status='active' WHERE username=?",
                (new_hash, ADMIN_USERNAME),
            )
            conn.commit()
            log.info("Admin user '%s' password synced from env.", ADMIN_USERNAME)

        # Ensure admin has a user_profiles row so they can generate proposals immediately
        admin_row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)
        ).fetchone()
        if admin_row:
            admin_id = admin_row["id"]
            profile_exists = conn.execute(
                "SELECT user_id FROM user_profiles WHERE user_id = ?", (admin_id,)
            ).fetchone()
            if not profile_exists:
                conn.execute(
                    "INSERT INTO user_profiles (user_id, full_name, designation, email) VALUES (?,?,?,?)",
                    (admin_id, "Admin", "Admin", "admin@fmr.local"),
                )
                conn.commit()
                log.info("Admin profile row created (placeholder — update via Profile page).")

    except Exception:
        log.exception("init_db() failed")
        raise
    finally:
        conn.close()
