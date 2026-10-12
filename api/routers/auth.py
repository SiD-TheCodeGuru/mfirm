import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status

from api.core.database import get_database
from api.core.security import hash_password, verify_password, create_access_token
from api.dependencies import get_current_user
from api.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserProfileOut,
    TokenResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Access"])


@router.post("/register", response_model=UserProfileOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterRequest, db=Depends(get_database)):
    # 1. Enforce business rules per role
    if payload.role == "firm_admin" and not payload.firm_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A firm_id is required when creating a firm_admin.",
        )
    if payload.role == "sys_admin" and payload.firm_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A sys_admin must have firm_id set to null.",
        )

    # 2. Check if firm exists if provided
    if payload.firm_id:
        firm_exists = await db.firms.find_one({"_id": payload.firm_id})
        if not firm_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Firm '{payload.firm_id}' does not exist.",
            )

    # 3. Check for uniqueness of username and email
    existing_user = await db.users.find_one({
        "$or": [{"username": payload.username}, {"email": payload.email}]
    })
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is already registered.",
        )

    # 4. Insert user
    user_id = f"USR_{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    user_doc = {
        "_id": user_id,
        "username": payload.username,
        "email": payload.email,
        "hashed_password": hash_password(payload.password),
        "full_name": payload.full_name,
        "phone": payload.phone,
        "role": payload.role,
        "firm_id": payload.firm_id if payload.role == "firm_admin" else None,
        "is_active": True,
        "last_login": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.users.insert_one(user_doc)

    return UserProfileOut(
        id=user_id,
        username=user_doc["username"],
        email=user_doc["email"],
        full_name=user_doc["full_name"],
        phone=user_doc["phone"],
        role=user_doc["role"],
        firm_id=user_doc["firm_id"],
        is_active=user_doc["is_active"],
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLoginRequest, db=Depends(get_database)):
    # 1. Look up user by username or email
    user = await db.users.find_one({
        "$or": [
            {"username": payload.username_or_email},
            {"email": payload.username_or_email},
        ]
    })

    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact system administrator.",
        )

    # 2. Update login timestamp
    now = datetime.now(timezone.utc)
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login": now}})

    # 3. Create JWT token
    token_claims = {
        "sub": user["_id"],
        "username": user["username"],
        "role": user["role"],
        "firm_id": user.get("firm_id"),
    }
    token = create_access_token(data=token_claims)

    user_profile = UserProfileOut(
        id=user["_id"],
        username=user["username"],
        email=user["email"],
        full_name=user["full_name"],
        phone=user.get("phone"),
        role=user["role"],
        firm_id=user.get("firm_id"),
        is_active=user["is_active"],
    )

    return TokenResponse(access_token=token, token_type="bearer", user=user_profile)


@router.get("/me", response_model=UserProfileOut)
async def get_profile(current_user: dict = Depends(get_current_user)):
    return UserProfileOut(
        id=current_user["_id"],
        username=current_user["username"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        phone=current_user.get("phone"),
        role=current_user["role"],
        firm_id=current_user.get("firm_id"),
        is_active=current_user["is_active"],
    )


@router.get("/available-firms")
async def list_available_firms(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Used by the mobile client to render the 'Switch Firm' picker.
    - sys_admin sees all active firms.
    - firm_admin sees only their own assigned firm.
    """
    if current_user["role"] == "sys_admin":
        cursor = db.firms.find({"is_active": True}, {"_id": 1, "firm_name": 1, "registration_code": 1})
        firms = await cursor.to_list(length=100)
        return [{"firm_id": f["_id"], "firm_name": f["firm_name"]} for f in firms]

    # firm_admin context
    firm = await db.firms.find_one({"_id": current_user["firm_id"]}, {"_id": 1, "firm_name": 1})
    if not firm:
        return []
    return [{"firm_id": firm["_id"], "firm_name": firm["firm_name"]}]