from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import ADMIN_SECRET_KEY

api_key_header = APIKeyHeader(name="X-Admin-Secret", auto_error=False)

async def verify_admin_permission(api_key: str = Security(api_key_header)):
    if api_key != ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative permission key required."
        )
    return True