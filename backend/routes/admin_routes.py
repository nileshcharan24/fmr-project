import shutil
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.auth import hash_password, require_admin
from backend.config import RESOURCES_DIR
from backend.database import get_db
from backend.services.resource_reader import (
    list_resources,
    read_cluster_descriptions,
    write_cluster_descriptions,
)

router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_RESOURCE_EXTENSIONS = {".docx", ".pptx", ".json", ".pdf", ".png", ".jpg", ".jpeg"}

# ── User management ──────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"


class ResetPasswordRequest(BaseModel):
    password: str


@router.post("/users")
def create_user(body: CreateUserRequest, _: dict = Depends(require_admin)):
    if body.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (body.username,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")

        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (body.username, hash_password(body.password), body.role),
        )
        row = conn.execute(
            "SELECT id, username, role, created_at FROM users WHERE username = ?",
            (body.username,),
        ).fetchone()

    return dict(row)


@router.get("/users")
def list_users(_: dict = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, role, status, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/users/pending")
def list_pending_users(_: dict = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, role, status, created_at FROM users WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, _: dict = Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        conn.execute("UPDATE users SET status = 'active' WHERE id = ?", (user_id,))
    return {"detail": "User approved"}


@router.post("/users/{user_id}/reject")
def reject_user(user_id: int, _: dict = Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        conn.execute("UPDATE users SET status = 'rejected' WHERE id = ?", (user_id,))
    return {"detail": "User rejected"}


@router.put("/users/{user_id}/password")
def reset_password(user_id: int, body: ResetPasswordRequest, current_admin: dict = Depends(require_admin)):
    if not body.password or len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(body.password), user_id),
        )
    return {"detail": "Password updated"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_admin: dict = Depends(require_admin)):
    if user_id == current_admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    return {"detail": "User deleted"}


@router.post("/users/{user_id}/reset-rate-limit")
def reset_rate_limit(user_id: int, _: dict = Depends(require_admin)):
    week_string = date.today().strftime("%Y-W%W")

    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        conn.execute(
            "UPDATE rate_limits SET count = 0 WHERE user_id = ? AND week_string = ?",
            (user_id, week_string),
        )

    return {"detail": f"Rate limit reset for user {user_id} for week {week_string}"}


# ── All proposals (admin view) ────────────────────────────────────────────────

@router.get("/proposals")
def list_all_proposals(_: dict = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT p.id, p.company_name, p.tier, p.clusters, p.status,
                      p.error_message, p.created_at, u.username
               FROM proposals p
               JOIN users u ON u.id = p.user_id
               ORDER BY p.created_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


# ── Resource file management ──────────────────────────────────────────────────

# IMPORTANT: specific routes must come before parameterised ones to avoid
# FastAPI matching "clusters" as a {filename} value.

@router.get("/resources/clusters")
def get_clusters(_: dict = Depends(require_admin)):
    return read_cluster_descriptions()


@router.put("/resources/clusters")
def update_clusters(data: dict, _: dict = Depends(require_admin)):
    if not isinstance(data, dict) or not data:
        raise HTTPException(status_code=400, detail="Body must be a non-empty JSON object")
    write_cluster_descriptions(data)
    return {"detail": "Cluster descriptions updated", "count": len(data)}


@router.get("/resources")
def get_resources(_: dict = Depends(require_admin)):
    return list_resources()


@router.post("/resources/upload")
async def upload_resource(
    file: UploadFile = File(...),
    folder: str = "templates",
    _: dict = Depends(require_admin),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_RESOURCE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{suffix}' not allowed. Allowed: {ALLOWED_RESOURCE_EXTENSIONS}",
        )

    allowed_folders = {"templates", "deliverables", "guidelines", "clusters"}
    if folder not in allowed_folders:
        raise HTTPException(status_code=400, detail=f"folder must be one of {allowed_folders}")

    dest_dir = RESOURCES_DIR / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename

    content = await file.read()
    dest_path.write_bytes(content)

    return {
        "detail": "File uploaded",
        "path": f"{folder}/{file.filename}",
        "size_kb": round(len(content) / 1024, 1),
    }


@router.get("/resources/{filename}")
def download_resource(filename: str, _: dict = Depends(require_admin)):
    # Search all subdirectories for the file
    for f in RESOURCES_DIR.rglob(filename):
        if f.is_file():
            return FileResponse(str(f), filename=filename)
    raise HTTPException(status_code=404, detail=f"Resource '{filename}' not found")


@router.delete("/resources/{filename}")
def delete_resource(filename: str, _: dict = Depends(require_admin)):
    # Protect the cluster JSON from accidental deletion via this endpoint
    if filename == "cluster_descriptions.json":
        raise HTTPException(
            status_code=400,
            detail="Use PUT /admin/resources/clusters to update cluster descriptions",
        )

    for f in RESOURCES_DIR.rglob(filename):
        if f.is_file():
            f.unlink()
            return {"detail": f"'{filename}' deleted"}

    raise HTTPException(status_code=404, detail=f"Resource '{filename}' not found")
