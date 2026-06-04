from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import secrets
import os

# JWT settings - use persistent secret key
JWT_SECRET_FILE = "jwt_secret.txt"

def get_or_create_secret_key():
    """Get or create a persistent JWT secret key"""
    # First try environment variable
    env_secret = os.getenv("JWT_SECRET")
    if env_secret:
        return env_secret
    
    # Try to read from file
    if os.path.exists(JWT_SECRET_FILE):
        try:
            with open(JWT_SECRET_FILE, "r", encoding="utf-8") as f:
                secret = f.read().strip()
                if secret:
                    return secret
        except Exception as e:
            print(f"Error reading JWT secret file: {e}")
    
    # Generate new secret and save it
    new_secret = secrets.token_urlsafe(32)
    try:
        with open(JWT_SECRET_FILE, "w", encoding="utf-8") as f:
            f.write(new_secret)
        print(f"Generated new JWT secret and saved to {JWT_SECRET_FILE}")
    except Exception as e:
        print(f"Warning: Could not save JWT secret to file: {e}")
        print("JWT secret will change on server restart. Set JWT_SECRET environment variable for persistence.")
    
    return new_secret

SECRET_KEY = get_or_create_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token_string(token: str) -> dict:
    """Verify JWT token from string and return payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_sub": False})
        # Convert sub back to int for compatibility
        if "sub" in payload and isinstance(payload["sub"], str):
            try:
                payload["sub"] = int(payload["sub"])
            except ValueError:
                pass
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid authentication token: {str(e)}")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return payload"""
    try:
        token = credentials.credentials
        return verify_token_string(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current authenticated user"""
    payload = verify_token(credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    # Convert string to int if needed
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
    return {"user_id": user_id, "username": payload.get("username")}

