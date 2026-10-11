import hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import DemoSession, User

bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + "$" + key.hex()

def verify_password(password: str, value: str) -> bool:
    try:
        salt_hex, key_hex = value.split("$", 1)
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(actual.hex(), key_hex)
    except (ValueError, TypeError):
        return False

def otp_hash(code: str) -> str:
    return hashlib.sha256((code + (settings.jwt_secret or "local-development-otp-pepper")).encode()).hexdigest()

def issue_token(user: User) -> str:
    if not settings.jwt_secret and settings.app_env == "production":
        raise HTTPException(503, "JWT_SECRET must be configured before authentication is available.")
    secret = settings.jwt_secret or "local-only-change-me-before-deployment"
    return jwt.encode({"sub": str(user.id), "typ": "user", "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes)}, secret, algorithm="HS256")

def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "Authentication required.")
    try:
        secret = settings.jwt_secret or "local-only-change-me-before-deployment"
        payload = jwt.decode(creds.credentials, secret, algorithms=["HS256"])
        if payload.get("typ") not in (None, "user"):
            raise ValueError("Not a user session")
        uid = payload.get("sub")
        user = db.get(User, int(uid))
    except Exception:
        user = None
    if not user or not user.is_active:
        raise HTTPException(401, "Invalid or expired session.")
    return user


def _demo_signing_key() -> bytes:
    if not settings.jwt_secret and settings.app_env == "production":
        raise HTTPException(503, "JWT_SECRET must be configured before demo sessions are available.")
    master = (settings.jwt_secret or "local-only-change-me-before-deployment").encode()
    return hmac.new(master, b"recycleproof-demo-session-v1", hashlib.sha256).digest()


def issue_demo_token(session_id: str, expires_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sid": session_id,
        "typ": "demo",
        "scope": ["demo"],
        "iss": "recycleproof",
        "aud": "recycleproof-demo",
        "iat": now,
        "exp": expires_at,
        "jti": secrets.token_urlsafe(18),
    }, _demo_signing_key(), algorithm="HS256")


def current_demo_session(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> DemoSession:
    if not creds:
        raise HTTPException(401, "Demo session required. Start a demo from the public landing page.")
    try:
        # Decode signature/audience/issuer, then explicitly check expiration so the
        # server can revoke the corresponding database session on first use.
        payload = jwt.decode(creds.credentials, _demo_signing_key(), algorithms=["HS256"],
                             audience="recycleproof-demo", issuer="recycleproof",
                             options={"verify_exp": False})
        if payload.get("typ") != "demo" or payload.get("scope") != ["demo"]:
            raise ValueError("Invalid demo scope")
        sid = payload.get("sid")
        exp = payload.get("exp")
        if not isinstance(sid, str) or not isinstance(exp, (int, float)):
            raise ValueError("Invalid demo identity")
        session = db.get(DemoSession, sid)
    except Exception as exc:
        raise HTTPException(401, "Invalid demo session. Start a fresh demo session.") from exc
    now = datetime.now(timezone.utc)
    row_expiry = session.expires_at.replace(tzinfo=timezone.utc) if session and session.expires_at.tzinfo is None else (session.expires_at if session else now)
    token_expiry = datetime.fromtimestamp(exp, timezone.utc)
    if not session:
        raise HTTPException(401, "Demo session is invalid. Start a fresh demo session.")
    if session.revoked_at or row_expiry <= now or token_expiry <= now:
        if not session.revoked_at:
            session.revoked_at = now
            db.commit()
        raise HTTPException(401, "Demo session expired or was revoked. Start a fresh demo session.")
    session.last_seen_at = now
    return session
