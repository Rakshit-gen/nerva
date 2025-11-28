"""
Security utilities - format validation only.
No password storage or auth logic per requirements.
"""
import uuid
import re
from fastapi import HTTPException, Header
from typing import Optional


def validate_uuid(value: str) -> bool:
    """Validate UUID format."""
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def validate_token_format(token: str) -> bool:
    """
    Validate token format (basic validation only).
    Actual token validation is handled by frontend/external auth.
    """
    if not token:
        return False
    # Token should be at least 20 chars and alphanumeric with common special chars
    if len(token) < 20:
        return False
    pattern = r'^[a-zA-Z0-9_\-\.]+$'
    return bool(re.match(pattern, token))


async def validate_user_token(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    authorization: Optional[str] = Header(None),
) -> str:
    """
    Dependency to validate user ID and token format.
    Returns the user_id if valid.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="X-User-ID header is required",
        )
    
    if not validate_uuid(x_user_id):
        raise HTTPException(
            status_code=401,
            detail="Invalid user ID format - must be UUID",
        )
    
    if authorization:
        # Extract token from "Bearer <token>" format
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            if not validate_token_format(token):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token format",
                )
    
    return x_user_id


def get_user_id_from_header(x_user_id: str = Header(..., alias="X-User-ID")) -> str:
    """Simple dependency to extract and validate user ID."""
    if not validate_uuid(x_user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID format",
        )
    return x_user_id
