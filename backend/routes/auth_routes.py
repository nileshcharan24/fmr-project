from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from backend.auth import authenticate_user, create_access_token, get_current_user, hash_password
from backend.config import (
    FRONTEND_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
)
from backend.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = ""
    designation: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""

import re as _re
_PHONE_RE = _re.compile(r"^\+\d{1,4} \d{5} \d{5}$")


@router.post("/login")
def login(body: LoginRequest):
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user.get("status") == "pending":
        raise HTTPException(status_code=403, detail="Your account is pending admin approval. You'll be notified once access is granted.")
    if user.get("status") == "rejected":
        raise HTTPException(status_code=403, detail="Your access request was rejected. Contact the admin.")
    token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    return {"token": token, "role": user["role"], "username": user["username"]}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        profile = conn.execute(
            "SELECT full_name, designation, phone, email FROM user_profiles WHERE user_id = ?",
            (current_user["id"],),
        ).fetchone()
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "full_name": profile["full_name"] if profile else "",
        "designation": profile["designation"] if profile else "",
        "phone": profile["phone"] if profile else "",
        "email": profile["email"] if profile else "",
    }


# ── Google OAuth ──────────────────────────────────────────────────────────────

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"
ALLOWED_DOMAIN   = "nitt.edu"   # .nitt@gmail.com addresses have hd=nitt.edu
ALLOWED_SUFFIX   = ".nitt@gmail.com"


@router.get("/google/login")
def google_login():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google OAuth is not configured on this server")
    params = (
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&prompt=select_account"
    )
    return RedirectResponse(GOOGLE_AUTH_URL + params)


@router.get("/google/callback")
async def google_callback(code: str = None, error: str = None):
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_cancelled")
    if not GOOGLE_CLIENT_ID:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=not_configured")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_res = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_res.status_code != 200:
            return RedirectResponse(f"{FRONTEND_URL}/login?error=token_exchange_failed")

        access_token = token_res.json().get("access_token")
        info_res = await client.get(GOOGLE_USERINFO,
                                    headers={"Authorization": f"Bearer {access_token}"})
        if info_res.status_code != 200:
            return RedirectResponse(f"{FRONTEND_URL}/login?error=userinfo_failed")

    info = info_res.json()
    email = info.get("email", "")

    # Enforce .nitt@gmail.com addresses only
    if not email.endswith(ALLOWED_SUFFIX):
        return RedirectResponse(f"{FRONTEND_URL}/login?error=domain_not_allowed")

    # username = everything before @gmail.com, e.g. "arjun.nitt"
    username = email.replace("@gmail.com", "")
    full_name = info.get("name", "")

    is_new_user = False
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            import secrets
            conn.execute(
                "INSERT INTO users (username, password_hash, role, status) VALUES (?,?,?,?)",
                (username, hash_password(secrets.token_hex(32)), "user", "pending"),
            )
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            is_new_user = True

        user_id = user["id"]

        # Upsert profile with Google name/email
        existing = conn.execute(
            "SELECT user_id FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            # Only update name/email if they're still blank
            conn.execute(
                """UPDATE user_profiles SET
                   full_name = CASE WHEN full_name = '' THEN ? ELSE full_name END,
                   email     = CASE WHEN email     = '' THEN ? ELSE email     END
                   WHERE user_id = ?""",
                (full_name, email, user_id),
            )
        else:
            conn.execute(
                "INSERT INTO user_profiles (user_id, full_name, email) VALUES (?,?,?)",
                (user_id, full_name, email),
            )

    # Block pending/rejected users from logging in via OAuth too
    if user["status"] == "pending":
        if is_new_user:
            return RedirectResponse(f"{FRONTEND_URL}/login?error=pending_approval")
        return RedirectResponse(f"{FRONTEND_URL}/login?error=still_pending")
    if user["status"] == "rejected":
        return RedirectResponse(f"{FRONTEND_URL}/login?error=rejected")

    jwt = create_access_token({"sub": str(user_id), "role": user["role"]})
    return RedirectResponse(f"{FRONTEND_URL}/login?token={jwt}&username={username}&role={user['role']}")


@router.put("/profile")
def update_profile(body: ProfileUpdate, current_user: dict = Depends(get_current_user)):
    if body.phone and not _PHONE_RE.match(body.phone):
        raise HTTPException(
            status_code=400,
            detail="Phone must be in format: +<country code> <5 digits> <5 digits>  e.g. +91 98765 43210",
        )

    with get_db() as conn:
        existing = conn.execute(
            "SELECT user_id, email FROM user_profiles WHERE user_id = ?", (current_user["id"],)
        ).fetchone()
        if existing:
            # Email is locked once set — ignore any new email value if one already exists
            locked_email = existing["email"] if existing["email"] else (body.email or "")
            conn.execute(
                """UPDATE user_profiles SET full_name=?, designation=?, phone=?, email=?
                   WHERE user_id=?""",
                (body.full_name, body.designation, body.phone, locked_email, current_user["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO user_profiles (user_id, full_name, designation, phone, email)
                   VALUES (?,?,?,?,?)""",
                (current_user["id"], body.full_name, body.designation, body.phone, body.email or ""),
            )
    return {"ok": True}
