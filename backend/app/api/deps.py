from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import User

SESSION_COOKIE = "vp_session"


def signer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt=salt)


def session_token(user_id: int) -> str:
    return signer("session").dumps(user_id)


def is_admin(user: User) -> bool:
    admins = {e.lower() for e in get_settings().admin_emails}
    return bool(user.email and user.email.lower() in admins)


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        user_id = signer("session").loads(token, max_age=get_settings().session_days * 86400)
    except BadSignature:
        return None
    return db.get(User, user_id)


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "not signed in")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not is_admin(user):
        raise HTTPException(403, "admin only")
    return user
