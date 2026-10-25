"""Password hashing, JWT handling and the FastAPI auth dependencies.

The user's role is NEVER taken from the request body or from the client. It comes from the
database row of the user identified by a verified, non-revoked JWT."""
import time
import uuid
from collections import defaultdict, deque

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import db
from app.config import settings

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt())


# ----------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Always performs one bcrypt check so unknown users take as long as known ones."""
    target = password_hash.encode() if password_hash else _DUMMY_HASH
    ok = bcrypt.checkpw(password.encode("utf-8")[:72], target)
    return ok and password_hash is not None


# ----------------------------------------------------------------- tokens
def create_token(user) -> tuple[str, float]:
    exp = time.time() + settings.jwt_expire_minutes * 60
    payload = {"sub": str(user["id"]), "role": user["role"], "jti": uuid.uuid4().hex, "pwv": user["pw_version"], "iat": int(time.time()), "exp": int(exp)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), exp


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "jti"]})


def _unauthorized(msg="Your session has expired. Please log in again."):
    return HTTPException(status.HTTP_401_UNAUTHORIZED, msg, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if creds is None:
        raise _unauthorized("Please log in to continue.")
    try:
        claims = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized()
    except jwt.PyJWTError:
        raise _unauthorized("Invalid login session. Please log in again.")
    if db.is_revoked(claims["jti"]):
        raise _unauthorized()
    user = db.get_user_by_id(int(claims["sub"]))
    if user is None or user["role"] != claims.get("role"):
        raise _unauthorized()  # user deleted, or role changed since the token was issued
    if claims.get("pwv", 0) != user["pw_version"]:
        raise _unauthorized()  # password was changed or reset: every older session is invalid
    out = dict(user)
    out["_jti"], out["_exp"] = claims["jti"], claims["exp"]
    return out


def require_role(role: str):
    def dep(user=Depends(get_current_user)):
        if user["role"] != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"This area is only for {role} accounts.")
        return user
    return dep


# ----------------------------------------------------------------- rate limiting (in-memory, single instance)
class SlidingWindow:
    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self.events = defaultdict(deque)

    def _trim(self, key):
        q, now = self.events[key], time.time()
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, key) -> bool:
        return len(self._trim(key)) >= self.limit

    def add(self, key):
        self._trim(key).append(time.time())

    def reset(self, key):
        self.events.pop(key, None)

    def retry_after(self, key) -> int:
        q = self._trim(key)
        return max(1, int(self.window - (time.time() - q[0]))) if q else 1


login_failures = SlidingWindow(limit=5, window=600)            # 5 wrong passwords / 10 min per (ip, username)
register_failures = SlidingWindow(limit=5, window=600)         # 5 wrong access codes / 10 min per IP
chat_limiter = SlidingWindow(limit=settings.chat_rate_per_minute, window=60)
