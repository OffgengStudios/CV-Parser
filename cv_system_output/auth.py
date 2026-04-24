"""
auth.py — JWT token generation, validation, and authentication middleware.

Provides:
- Token creation and verification (with per-token jti for revocation)
- In-memory JWT denylist for logout (auto-pruned when tokens expire)
- HTTP Bearer authentication dependency
- Default demo credentials (for development, gated by ENABLE_DEMO_CREDENTIALS)
- Production-ready structure for database lookups
"""
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import crud
from database.models import WorkerUser
from database.session import get_db
from logger import get_logger

log = get_logger(__name__)

# Configuration — single source of truth via config.py / .env
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = settings.ACCESS_TOKEN_EXPIRE_HOURS
PASSWORD_HASH_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "260000"))

# Demo credentials for development (in production, query database)
DEMO_USERS = {
    "admin": "admin123",
    "demo": "demo123",
}

# ---------------------------------------------------------------------------
# JWT denylist — maps jti (JWT ID) → expiry timestamp (UTC epoch seconds).
# Tokens are added here on logout; verify_token rejects any listed jti.
# Entries whose expiry has passed are pruned automatically so the dict never
# grows unboundedly even under a long-running process.
# ---------------------------------------------------------------------------
_token_denylist: dict[str, float] = {}


def _prune_denylist() -> None:
    """Remove expired entries from the denylist (called opportunistically)."""
    now = datetime.now(timezone.utc).timestamp()
    expired = [jti for jti, exp in _token_denylist.items() if exp <= now]
    for jti in expired:
        del _token_denylist[jti]


def revoke_token(jti: str, exp_timestamp: float) -> None:
    """
    Add a token JTI to the denylist so it is rejected on future requests.

    Args:
        jti: The unique token ID from the JWT payload.
        exp_timestamp: The token's expiry as a UTC epoch float (from the 'exp' claim).
    """
    _prune_denylist()
    _token_denylist[jti] = exp_timestamp
    log.debug(f"Token revoked: jti={jti}, denylist_size={len(_token_denylist)}")


def is_token_revoked(jti: str) -> bool:
    """Return True if the given jti has been revoked."""
    return jti in _token_denylist


# ============================================================================
# Schemas
# ============================================================================


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenData(BaseModel):
    """Decoded JWT payload."""
    user_id: str | None = None
    jti: str | None = None
    exp: datetime | None = None


class LoginRequest(BaseModel):
    """Login endpoint request."""
    username: str
    password: str


class CreateWorkerUserRequest(BaseModel):
    """Admin request to create a worker login."""
    username: str
    password: str
    full_name: str | None = None
    is_admin: bool = False


class ResetPasswordRequest(BaseModel):
    """Admin request to reset a worker's password."""
    new_password: str


class WorkerUserResponse(BaseModel):
    """Worker user response without secret fields."""
    username: str
    full_name: str | None = None
    is_admin: bool
    is_active: bool
    created_by: str | None = None
    created_at: datetime | None = None


# ============================================================================
# Token operations
# ============================================================================


def create_access_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, int]:
    """
    Create a JWT access token with a unique jti claim for revocation support.

    Args:
        user_id: User identifier to encode in token.
        expires_delta: Token expiration time. Defaults to ACCESS_TOKEN_EXPIRE_HOURS.

    Returns:
        Tuple of (token_string, expires_in_seconds)
    """
    if expires_delta is None:
        expires_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    expire = datetime.now(timezone.utc) + expires_delta
    token_jti = str(uuid.uuid4())
    to_encode = {
        "user_id": user_id,
        "jti": token_jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    expires_in_seconds = int(expires_delta.total_seconds())
    return encoded_jwt, expires_in_seconds


def verify_token(token: str) -> TokenData:
    """
    Verify and decode a JWT token, rejecting revoked tokens.

    Args:
        token: JWT token string (without "Bearer " prefix).

    Returns:
        TokenData with user_id and jti from token.

    Raises:
        JWTError: If token is invalid, expired, or has been revoked.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("user_id")
        token_jti: str | None = payload.get("jti")

        if user_id is None:
            raise JWTError("Missing 'user_id' in token")

        # Reject tokens that have been explicitly revoked (e.g., after logout)
        if token_jti and is_token_revoked(token_jti):
            raise JWTError(f"Token has been revoked (jti={token_jti})")

        exp_raw = payload.get("exp")
        exp_dt = (
            datetime.fromtimestamp(exp_raw, tz=timezone.utc)
            if isinstance(exp_raw, (int, float))
            else None
        )
        return TokenData(user_id=user_id, jti=token_jti, exp=exp_dt)
    except JWTError as e:
        log.warning(f"Invalid token: {e}")
        raise


# ============================================================================
# Authentication dependency
# ============================================================================


# HTTP Bearer scheme for OpenAPI/Swagger
security = HTTPBearer(description="JWT Bearer token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    FastAPI dependency to extract and validate the current user from Bearer token.

    Args:
        credentials: HTTP Bearer credentials from Authorization header.

    Returns:
        user_id from verified token.

    Raises:
        HTTPException: 401 Unauthorized if token is invalid, expired, or revoked.
    """
    token = credentials.credentials
    try:
        token_data = verify_token(token)
        if token_data.user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token_data.user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_with_token_data(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """
    Like get_current_user but returns the full TokenData (including jti).
    Used by the logout and refresh endpoints which need the jti for revocation.
    """
    token = credentials.credentials
    try:
        token_data = verify_token(token)
        if token_data.user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token_data
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_admin_user(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> str:
    """Allow the built-in admin and database users marked as admins."""
    if current_user == "admin":
        return current_user

    user = crud.get_worker_user(db, current_user)
    if user and user.is_admin and user.is_active:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin privileges are required.",
    )


# ============================================================================
# Credential verification
# ============================================================================


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a per-user salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a PBKDF2 password hash."""
    try:
        algorithm, iterations_value, salt, expected_digest = password_hash.split("$", 3)
        iterations = int(iterations_value)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(actual_digest, expected_digest)


def verify_credentials(username: str, password: str, db: Session | None = None) -> bool:
    """
    Verify username and password against allowed credentials.

    In development: Check DEMO_USERS hardcoded dict.
    In production: Query a database or external auth service.

    Args:
        username: Username to verify.
        password: Password to verify.

    Returns:
        True if credentials are valid, False otherwise.
    """
    if db is not None:
        user = crud.get_worker_user(db, username)
        if user and user.is_active and verify_password(password, user.password_hash):
            return True

    # Built-in fallback credentials — only active when ENABLE_DEMO_CREDENTIALS=true.
    # Use hmac.compare_digest to prevent timing side-channel attacks.
    if settings.ENABLE_DEMO_CREDENTIALS:
        expected = DEMO_USERS.get(username, "")
        if expected and hmac.compare_digest(expected, password):
            return True

    log.warning(f"Failed login attempt for username: {username}")
    return False


def is_builtin_user(username: str) -> bool:
    return username in DEMO_USERS
