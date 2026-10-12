from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from api.core.database import get_database
from api.core.security import decode_access_token

security = HTTPBearer(auto_error=True)


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db=Depends(get_database),
) -> dict:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is missing user identifier (sub)",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token does not exist.",
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


async def get_active_firm_context(
        current_user: dict = Depends(get_current_user),
        x_active_firm_id: Optional[str] = Header(
            None,
            alias="X-Active-Firm-ID",
            description="Header required for sys_admin to select active firm",
        ),
        db=Depends(get_database),
) -> dict:
    """
    Resolves the operational tenant context for downstream routes.
    Returns a dictionary containing:
      - 'firm_id': The confirmed active firm identifier.
      - 'user_id': Caller's unique user ID.
      - 'role': Caller's system role.
      - 'user': The full current user document.
    """
    user_role = current_user.get("role")

    if user_role == "firm_admin":
        firm_id = current_user.get("firm_id")
        if not firm_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Firm admin configuration error: no firm_id assigned.",
            )

        # Verify that the assigned firm is active
        firm = await db.firms.find_one({"_id": firm_id})
        if not firm or not firm.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your firm is inactive or suspended.",
            )

        return {
            "firm_id": firm_id,
            "user_id": current_user["_id"],
            "role": user_role,
            "user": current_user,
        }

    elif user_role == "sys_admin":
        if not x_active_firm_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="System Admin must select an active firm. Pass 'X-Active-Firm-ID' header.",
            )

        # Validate that the requested target firm exists
        target_firm = await db.firms.find_one({"_id": x_active_firm_id})
        if not target_firm:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target firm '{x_active_firm_id}' does not exist.",
            )
        if not target_firm.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target firm '{x_active_firm_id}' is suspended/inactive.",
            )

        return {
            "firm_id": x_active_firm_id,
            "user_id": current_user["_id"],
            "role": user_role,
            "user": current_user,
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized role.",
        )