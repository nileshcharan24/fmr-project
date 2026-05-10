import sqlite3
from contextlib import contextmanager
from backend.config import DATABASE_PATH


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
    """Run one-time schema migrations that ALTER TABLE cannot do via CREATE IF NOT EXISTS."""
    conn.execute("DROP TABLE IF EXISTS draft_sessions")

    # users: add status column
    user_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "status" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")

    # proposals: add background-job columns
    proposal_cols = [r[1] for r in conn.execute("PRAGMA table_info(proposals)").fetchall()]
    for col, definition in [
        ("job_id",              "TEXT"),
        ("folder_name",         "TEXT DEFAULT ''"),
        ("cover_letter",        "TEXT DEFAULT ''"),
        ("fest_deliverables",   "TEXT DEFAULT ''"),
        ("company_deliverables","TEXT DEFAULT ''"),
    ]:
        if col not in proposal_cols:
            conn.execute(f"ALTER TABLE proposals ADD COLUMN {col} {definition}")


def init_db():
    with get_db() as conn:
        _migrate(conn)
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
                id                   TEXT    PRIMARY KEY,
                user_id              INTEGER NOT NULL,
                company_name         TEXT    NOT NULL,
                tier                 INTEGER NOT NULL,
                clusters             TEXT    NOT NULL,
                banner_count         INTEGER NOT NULL,
                logo_path            TEXT    DEFAULT '',
                manager_name         TEXT    DEFAULT '',
                manager_designation  TEXT    DEFAULT '',
                manager_phone        TEXT    DEFAULT '',
                manager_email        TEXT    DEFAULT '',
                outreach_city        TEXT    DEFAULT 'Bangalore',
                include_csr          INTEGER DEFAULT 0,
                extra_context        TEXT    DEFAULT '',
                llm_questions        TEXT    DEFAULT '',
                fest_deliverables    TEXT    DEFAULT '',
                company_deliverables TEXT    DEFAULT '',
                brand_event_description TEXT DEFAULT '',
                portfolio_name       TEXT    DEFAULT '',
                created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)
