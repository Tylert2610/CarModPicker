from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser
from app.api.schemas.token import TokenData
from app.core.config import settings
from app.db.session import get_db

ALGORITHM = settings.HASH_ALGORITHM


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/token")

# --- Password Utilities ---


def verify_password(plain_password: str, hashed_password_str: str) -> bool:
    """Verifies a plain password against a hashed password."""
    # Ensure hashed_password_str is bytes, as bcrypt expects
    hashed_password_bytes = hashed_password_str.encode("utf-8")
    plain_password_bytes = plain_password.encode("utf-8")
    return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)


def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    # Store as string
    return hashed_bytes.decode("utf-8")


# --- JWT Utilities ---


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Use default expiration from settings
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.HASH_ALGORITHM
    )
    return str(encoded_jwt)


# --- Dependency to Get Current User ---


async def get_current_user(
    access_token: Optional[str] = Cookie(None),  # Read "access_token" cookie
    db: Session = Depends(get_db),
) -> DBUser:
    """
    Decodes JWT token from cookie, validates credentials, and returns the user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if access_token is None:
        raise credentials_exception

    try:
        payload = jwt.decode(
            access_token, settings.SECRET_KEY, algorithms=[settings.HASH_ALGORITHM]
        )
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = db.query(DBUser).filter(DBUser.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return user


async def get_current_active_user_optional(
    access_token: Optional[str] = Cookie(None),  # Read "access_token" cookie
    db: Session = Depends(get_db),
) -> Optional[DBUser]:
    """
    Optionally returns the current active user if a valid token cookie is present.
    Returns None if no token, token is invalid/expired, user not found, or user is inactive.
    """
    if access_token is None:
        return None
    try:
        payload = jwt.decode(
            access_token, settings.SECRET_KEY, algorithms=[settings.HASH_ALGORITHM]
        )
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None  # Invalid token payload
        token_data = TokenData(username=username)
    except JWTError:  # Covers expired, invalid signature, etc.
        return None  # Token is invalid or expired

    user = db.query(DBUser).filter(DBUser.username == token_data.username).first()
    if user is None:
        return None  # User from token not found in DB

    if user.disabled:
        return None  # User is inactive, so not considered an "active user"

    return user
