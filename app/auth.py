"""
Authentication: signup, login, logout, session management, decorators.

Sessions live in Flask's signed cookie — keyed on user_id. Passwords hashed
with werkzeug.security (PBKDF2-SHA256).

First user to sign up becomes admin automatically. Subsequent signups are
'user' role. Toggle off public signups via env: SQA_ALLOW_SIGNUP=false.
"""
from __future__ import annotations

import os
import re
import uuid
from functools import wraps
from typing import Any, Callable

from flask import g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def signup_allowed() -> bool:
    """Public signup is on by default. Set SQA_ALLOW_SIGNUP=false to lock it
    down (e.g., once your team has all signed up). Always permit signup when
    the database is empty so the very first user can get in."""
    if _user_count() == 0:
        return True
    return os.environ.get("SQA_ALLOW_SIGNUP", "true").lower() not in ("0", "false", "no")


def _user_count() -> int:
    row = db.fetch_one("SELECT COUNT(*) AS n FROM users")
    return row["n"] if row else 0


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def create_user(email: str, password: str, name: str = "") -> dict[str, Any]:
    """Create a new account. All accounts are equal QA users — no admin role."""
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if db.fetch_one("SELECT id FROM users WHERE email = %s", (email,)):
        raise ValueError("An account with that email already exists.")

    user_id = uuid.uuid4().hex[:12]
    # All users get role='user'. The 'role' column is preserved on the table for
    # forward compatibility but is no longer used to gate any feature.
    db.execute(
        "INSERT INTO users (id, email, name, password_hash, role) VALUES (%s, %s, %s, %s, %s)",
        (user_id, email, name.strip()[:80], generate_password_hash(password), "user"),
    )
    return get_user(user_id)


def get_user(user_id: str) -> dict[str, Any] | None:
    return db.fetch_one(
        "SELECT id, email, name, role, created_at, last_login_at FROM users WHERE id = %s",
        (user_id,),
    )


def authenticate(email: str, password: str) -> dict[str, Any] | None:
    email = (email or "").strip().lower()
    row = db.fetch_one(
        "SELECT id, password_hash FROM users WHERE email = %s", (email,))
    if not row or not check_password_hash(row["password_hash"], password or ""):
        return None
    db.execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (row["id"],))
    return get_user(row["id"])


# ---------------------------------------------------------------------------
# Flask integration
# ---------------------------------------------------------------------------
def login_user(user: dict[str, Any]) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True


def logout_user() -> None:
    session.clear()


def load_current_user() -> None:
    """Populate g.user from session — to be called as a before_request hook."""
    g.user = None
    uid = session.get("user_id")
    if uid:
        g.user = get_user(uid)
        if not g.user:
            session.clear()


def login_required(view: Callable) -> Callable:
    """Decorator that bounces unauthenticated requests to /login."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "user", None):
            # Save the original URL so we can redirect back after login.
            session["next"] = request.url if request.method == "GET" else None
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "user", None):
            return redirect(url_for("login"))
        if g.user.get("role") != "admin":
            from flask import abort; abort(403)
        return view(*args, **kwargs)
    return wrapped


def current_user_id() -> str:
    return g.user["id"] if getattr(g, "user", None) else ""


def is_admin() -> bool:
    """Admin role is no longer used. Always returns False so any legacy
    callers fall back to owner-only access."""
    return False
