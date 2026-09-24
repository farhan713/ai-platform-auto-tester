"""
Authentication: signup, login, logout, session management, decorators.

Sessions live in Flask's signed cookie — keyed on user_id. Passwords hashed
with werkzeug.security (PBKDF2-SHA256).

Two roles:
  admin    — full access to every page.
  celerant — Dashboard, Activity Logs and SQL Dev only.

Role comes from users.role, with two overrides: any email listed in
SQA_ADMIN_EMAILS is always admin (bootstrap, so the first admin can exist
without touching the database), and the legacy 'user' role counts as
celerant. The first account on an empty database is created as admin.
Toggle off public signups via env: SQA_ALLOW_SIGNUP=false.
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

ROLE_ADMIN = "admin"
ROLE_CELERANT = "celerant"
ROLES = (ROLE_ADMIN, ROLE_CELERANT)


def admin_emails() -> set[str]:
    """Emails that are always admin, from SQA_ADMIN_EMAILS (comma separated)."""
    raw = os.environ.get("SQA_ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def effective_role(user: dict[str, Any] | None) -> str:
    """Role actually applied. Anything that isn't admin is celerant, so the
    legacy 'user' role needs no migration."""
    if not user:
        return ""
    if (user.get("email") or "").strip().lower() in admin_emails():
        return ROLE_ADMIN
    return ROLE_ADMIN if user.get("role") == ROLE_ADMIN else ROLE_CELERANT


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
def create_user(email: str, password: str, name: str = "", role: str | None = None) -> dict[str, Any]:
    """Create a new account. Celerant role by default; admin for the first
    account on an empty database or for an email in SQA_ADMIN_EMAILS."""
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if db.fetch_one("SELECT id FROM users WHERE email = %s", (email,)):
        raise ValueError("An account with that email already exists.")

    if role not in ROLES:
        role = ROLE_ADMIN if (_user_count() == 0 or email in admin_emails()) else ROLE_CELERANT
    user_id = uuid.uuid4().hex[:12]
    db.execute(
        "INSERT INTO users (id, email, name, password_hash, role) VALUES (%s, %s, %s, %s, %s)",
        (user_id, email, name.strip()[:80], generate_password_hash(password), role),
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
        if effective_role(g.user) != ROLE_ADMIN:
            from flask import abort; abort(403)
        return view(*args, **kwargs)
    return wrapped


def current_user_id() -> str:
    return g.user["id"] if getattr(g, "user", None) else ""


def is_admin() -> bool:
    return effective_role(getattr(g, "user", None)) == ROLE_ADMIN
