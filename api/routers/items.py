from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.core.database import get_database
from api.dependencies import get_current_user
from api.schemas.item import ItemRegisterRequest, ItemUpdateRequest, ItemListOut

router = APIRouter(prefix="/api/v1/items", tags=["Inventory & Items"])

# Allowed unit enum according to MongoDB schema validator:
VALID_UNITS = {"ltr", "kg", "packets", "bags", "bottles", "pieces"}

def resolve_firm_context(current_user: dict, requested_firm_id: str = None) -> str:
    user_role = current_user.get("role")
    user_firm = current_user.get("firm_id")

    if user_role == "firm_admin":
        if not user_firm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account does not have an assigned firm_id.",
            )
        return user_firm

    if user_role == "sys_admin":
        if requested_firm_id:
            return requested_firm_id
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="firm_id must be provided for sys_admin context.",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient role permissions.",
    )


# -------------------------------------------------------------------------
# 1. Register Item
# -------------------------------------------------------------------------
@router.post("/register", response_model=ItemListOut, status_code=status.HTTP_201_CREATED)
async def register_item(
    payload: ItemRegisterRequest,
    firm_id: Optional[str] = Query(None, description="Target firm ID (required only for sys_admin)"),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    target_firm_id = resolve_firm_context(current_user, firm_id)

    # Normalize and validate default_unit against Mongo validator enum
    unit = payload.default_unit.strip().lower()
    # Normalize common singular to plural if user selects packet / bottle / piece / bag
    plural_map = {"packet": "packets", "bottle": "bottles", "piece": "pieces", "bag": "bags"}
    unit = plural_map.get(unit, unit)

    if unit not in VALID_UNITS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid default_unit '{unit}'. Must be one of: {sorted(list(VALID_UNITS))}",
        )

    # Check for duplicates within the same firm
    existing_item = await db.items.find_one({
        "firm_id": target_firm_id,
        "item_name": {"$regex": f"^{payload.item_name.strip()}$", "$options": "i"}
    })
    if existing_item:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item with name '{payload.item_name}' already exists in this firm.",
        )

    item_id = f"ITM_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:4].upper()}"
    now_dt = datetime.now(timezone.utc)

    item_doc = {
        "_id": item_id,
        "item_id": item_id,
        "item_name": payload.item_name.strip(),
        "category": payload.category.strip(),
        "default_unit": unit,
        "remarks": payload.remarks.strip() if payload.remarks else None,
        "firm_id": target_firm_id,
        "user_id": current_user["_id"],
        "entry_dtm": now_dt,       # BSON Date object
        "udate_dtm": now_dt,       # Note 'udate_dtm' as required by MongoDB validator
    }

    await db.items.insert_one(item_doc)

    # Convert BSON dates to ISO string for Pydantic response model
    return {
        **item_doc,
        "entry_dtm": item_doc["entry_dtm"].isoformat(),
        "udate_dtm": item_doc["udate_dtm"].isoformat(),
    }


# -------------------------------------------------------------------------
# 2. List Items by Firm
# -------------------------------------------------------------------------
@router.get("/by-firm/{firm_id}", response_model=List[ItemListOut], status_code=status.HTTP_200_OK)
async def list_items_by_firm(
    firm_id: str,
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    user_role = current_user.get("role")
    user_firm = current_user.get("firm_id")

    if user_role == "firm_admin" and user_firm != firm_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You cannot view items of another firm.",
        )

    cursor = db.items.find({"firm_id": firm_id}).sort("item_name", 1)
    items = await cursor.to_list(length=1000)

    response_items = []
    for item in items:
        # Handle BSON Date conversion to ISO string
        entry_dtm = item.get("entry_dtm")
        if isinstance(entry_dtm, datetime):
            entry_dtm = entry_dtm.isoformat()

        udate_dtm = item.get("udate_dtm")
        if isinstance(udate_dtm, datetime):
            udate_dtm = udate_dtm.isoformat()

        response_items.append({
            "item_id": str(item.get("_id", item.get("item_id"))),
            "item_name": item["item_name"],
            "category": item["category"],
            "default_unit": item["default_unit"],
            "remarks": item.get("remarks"),
            "firm_id": item["firm_id"],
            "user_id": item["user_id"],
            "entry_dtm": entry_dtm or "",
            "udate_dtm": udate_dtm or "",
        })

    return response_items


# -------------------------------------------------------------------------
# 3. Edit / Update Item
# -------------------------------------------------------------------------
@router.put("/{item_id}", response_model=ItemListOut, status_code=status.HTTP_200_OK)
async def update_item(
    item_id: str,
    payload: ItemUpdateRequest,
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    existing_item = await db.items.find_one({"_id": item_id})
    if not existing_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")

    user_role = current_user.get("role")
    user_firm = current_user.get("firm_id")
    if user_role == "firm_admin" and user_firm != existing_item["firm_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden.")

    update_data = {}
    if payload.item_name is not None:
        clean_name = payload.item_name.strip()
        duplicate = await db.items.find_one({
            "_id": {"$ne": item_id},
            "firm_id": existing_item["firm_id"],
            "item_name": {"$regex": f"^{clean_name}$", "$options": "i"}
        })
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another item with name '{clean_name}' already exists in this firm.",
            )
        update_data["item_name"] = clean_name

    if payload.category is not None:
        update_data["category"] = payload.category.strip()

    if payload.default_unit is not None:
        unit = payload.default_unit.strip().lower()
        plural_map = {"packet": "packets", "bottle": "bottles", "piece": "pieces", "bag": "bags"}
        unit = plural_map.get(unit, unit)
        if unit not in VALID_UNITS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid unit. Allowed: {sorted(list(VALID_UNITS))}",
            )
        update_data["default_unit"] = unit

    if payload.remarks is not None:
        update_data["remarks"] = payload.remarks.strip()

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update.")

    now_dt = datetime.now(timezone.utc)
    update_data["udate_dtm"] = now_dt  # Update BSON Date

    updated_doc = await db.items.find_one_and_update(
        {"_id": item_id},
        {"$set": update_data},
        return_document=True,
    )

    entry_dtm = updated_doc.get("entry_dtm")
    if isinstance(entry_dtm, datetime):
        entry_dtm = entry_dtm.isoformat()

    udate_dtm = updated_doc.get("udate_dtm")
    if isinstance(udate_dtm, datetime):
        udate_dtm = udate_dtm.isoformat()

    return {
        "item_id": str(updated_doc.get("_id", updated_doc.get("item_id"))),
        "item_name": updated_doc["item_name"],
        "category": updated_doc["category"],
        "default_unit": updated_doc["default_unit"],
        "remarks": updated_doc.get("remarks"),
        "firm_id": updated_doc["firm_id"],
        "user_id": updated_doc["user_id"],
        "entry_dtm": entry_dtm or "",
        "udate_dtm": udate_dtm or "",
    }