from __future__ import annotations

from functools import wraps
from typing import Optional

from flask import g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from env_utils import get_env
from user_service import user_service


def _secret_key() -> str:
    return get_env("APP_SECRET_KEY", "smart-opd-dev-secret")


def _token_ttl_seconds() -> int:
    return int(get_env("ACCESS_TOKEN_TTL_SECONDS", "28800"))


SERIALIZER = URLSafeTimedSerializer(_secret_key(), salt="smart-opd-auth")


def authenticate(username: str, password: str) -> Optional[dict]:
    return user_service.authenticate(username, password)


def issue_token(user: dict) -> str:
    payload = {
        "user_id": user["user_id"],
        "session_version": user.get("session_version", 1),
    }
    return SERIALIZER.dumps(payload)


def parse_token(token: str) -> Optional[dict]:
    try:
        payload = SERIALIZER.loads(token, max_age=_token_ttl_seconds())
    except (BadSignature, SignatureExpired):
        return None
    user = user_service.get_user_by_id(payload.get("user_id", ""))
    if user is None:
        return None
    if user.get("session_version", 1) != payload.get("session_version", 1):
        return None
    return user


def current_user() -> Optional[dict]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    return parse_token(token)


def require_roles(*allowed_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({"message": "Authentication required"}), 401
            if user["role"] not in allowed_roles:
                return jsonify({"message": "Forbidden"}), 403
            g.current_user = user
            return func(*args, **kwargs)

        return wrapper

    return decorator
