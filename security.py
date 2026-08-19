import os
import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional
try:
    import jwt
    JWTError = jwt.PyJWTError
except Exception:
    from jose import jwt, JWTError
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import get_db, User

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-feynman-key-1337-prep")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

security_scheme = HTTPBearer()

def check_password_strength(password: str) -> bool:
    """
    Password policy:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

def validate_email_format(email: str) -> bool:
    """RFC-compliant basic email format validator."""
    # Simple RFC 5322 regex
    regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(regex, email))

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def hash_token(token: str) -> str:
    """Hashes a verification/reset token before saving to database."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    if isinstance(encoded_jwt, bytes):
        encoded_jwt = encoded_jwt.decode('utf-8')
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception as e:
        print(f"[JWT DECODE ERROR] {e}")
        return None

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    if isinstance(encoded_jwt, bytes):
        encoded_jwt = encoded_jwt.decode('utf-8')
    return encoded_jwt

def decode_refresh_token(token: str) -> Optional[dict]:
    try:
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except Exception as e:
        print(f"[REFRESH TOKEN DECODE ERROR] {e}")
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
