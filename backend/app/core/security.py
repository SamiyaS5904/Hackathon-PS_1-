"""Password hashing (scrypt, standard library) and signed login tokens (JWT, HS256)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

import jwt

from app.core.config import APP_SECRET, TOKEN_DAYS

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        salt, digest = base64.b64decode(salt_b64), base64.b64decode(digest_b64)
    except ValueError:
        return False
    test = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=len(digest))
    return hmac.compare_digest(test, digest)


def create_token(user_id: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + TOKEN_DAYS * 86400}, APP_SECRET, algorithm="HS256")


def decode_token(token: str) -> str | None:
    """User id from a valid token, else None."""
    try:
        return jwt.decode(token, APP_SECRET, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        return None
