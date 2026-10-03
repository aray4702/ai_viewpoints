"""Email magic-link and Discord OAuth sign-in. Sessions are signed cookies."""

import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE, current_user, is_admin, session_token, signer
from app.api.schemas import UserOut
from app.core.config import get_settings
from app.core.db import get_db
from app.delivery.email import send_email
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

MAGIC_LINK_MINUTES = 15
DISCORD_API = "https://discord.com/api"
OAUTH_STATE_COOKIE = "vp_oauth_state"


def _signed_in(user: User) -> RedirectResponse:
    s = get_settings()
    resp = RedirectResponse(s.web_base_url + "/", status_code=303)
    resp.set_cookie(
        SESSION_COOKIE,
        session_token(user.id),
        max_age=s.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=s.web_base_url.startswith("https"),
    )
    return resp


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, discord_id=user.discord_id, is_admin=is_admin(user)
    )


class MagicLinkIn(BaseModel):
    email: EmailStr


@router.post("/magic-link", status_code=204)
def request_magic_link(body: MagicLinkIn):
    s = get_settings()
    token = signer("magic").dumps(body.email.lower())
    link = f"{s.web_base_url}/api/auth/verify?token={token}"
    send_email(
        body.email,
        "Your sign-in link",
        f'<p><a href="{link}">Sign in to Their Take</a>. '
        f"The link expires in {MAGIC_LINK_MINUTES} minutes.</p>",
        text=f"Sign in to Their Take: {link}",
    )


@router.get("/verify")
def verify_magic_link(token: str, db: Session = Depends(get_db)):
    try:
        email = signer("magic").loads(token, max_age=MAGIC_LINK_MINUTES * 60)
    except SignatureExpired:
        raise HTTPException(400, "link expired") from None
    except BadSignature:
        raise HTTPException(400, "invalid link") from None
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        db.add(user)
        db.flush()
    return _signed_in(user)


@router.get("/discord/login")
def discord_login():
    s = get_settings()
    if not s.discord_client_id:
        raise HTTPException(501, "Discord login not configured")
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": s.discord_client_id,
        "redirect_uri": f"{s.web_base_url}/api/auth/discord/callback",
        "response_type": "code",
        "scope": "identify email",
        "state": state,
    }
    resp = RedirectResponse(f"{DISCORD_API}/oauth2/authorize?{urlencode(params)}")
    resp.set_cookie(OAUTH_STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax")
    return resp


@router.get("/discord/callback")
def discord_callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    if not secrets.compare_digest(state, request.cookies.get(OAUTH_STATE_COOKIE, "")):
        raise HTTPException(400, "bad OAuth state")
    tok = httpx.post(
        f"{DISCORD_API}/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{s.web_base_url}/api/auth/discord/callback",
        },
        auth=(s.discord_client_id, s.discord_client_secret),
        timeout=20,
    )
    tok.raise_for_status()
    me = httpx.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {tok.json()['access_token']}"},
        timeout=20,
    )
    me.raise_for_status()
    info = me.json()
    email = info.get("email").lower() if info.get("verified") and info.get("email") else None

    user = db.scalar(select(User).where(User.discord_id == info["id"]))
    if user is None and email:  # link to an existing email account
        user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        db.add(user)
    user.discord_id = info["id"]
    db.flush()
    resp = _signed_in(user)
    resp.delete_cookie(OAUTH_STATE_COOKIE)
    return resp


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user)
