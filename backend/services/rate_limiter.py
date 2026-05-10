from datetime import date

from backend.config import WEEKLY_LIMIT
from backend.database import get_db


def _current_week() -> str:
    return date.today().strftime("%Y-W%W")


def get_usage(user_id: int) -> dict:
    """Return current week's usage for a user."""
    week = _current_week()
    with get_db() as conn:
        row = conn.execute(
            "SELECT count FROM rate_limits WHERE user_id = ? AND week_string = ?",
            (user_id, week),
        ).fetchone()

    used = row["count"] if row else 0
    # Calculate next Monday
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    from datetime import timedelta
    resets_on = (today + timedelta(days=days_until_monday)).isoformat()

    return {"used": used, "limit": WEEKLY_LIMIT, "resets_on": resets_on}


def check_and_increment(user_id: int) -> None:
    """Raise an exception if limit is hit, otherwise increment count."""
    from fastapi import HTTPException

    week = _current_week()
    with get_db() as conn:
        row = conn.execute(
            "SELECT count FROM rate_limits WHERE user_id = ? AND week_string = ?",
            (user_id, week),
        ).fetchone()

        count = row["count"] if row else 0
        if count >= WEEKLY_LIMIT:
            usage = get_usage(user_id)
            raise HTTPException(
                status_code=429,
                detail=(
                    f"You've used {count}/{WEEKLY_LIMIT} proposals this week. "
                    f"Resets on {usage['resets_on']}."
                ),
            )

        if row:
            conn.execute(
                "UPDATE rate_limits SET count = count + 1 WHERE user_id = ? AND week_string = ?",
                (user_id, week),
            )
        else:
            conn.execute(
                "INSERT INTO rate_limits (user_id, week_string, count) VALUES (?, ?, 1)",
                (user_id, week),
            )
