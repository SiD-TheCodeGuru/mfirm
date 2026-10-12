from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.core.database import get_database
from api.dependencies import get_current_user
from api.schemas.stock import StockAdjustmentRequest, StockItemOut

router = APIRouter(prefix="/api/v1/stocks", tags=["Stock Management"])

def resolve_firm_context(current_user: dict, requested_firm_id: str = None) -> str:
    user_role = current_user.get("role")
    user_firm = current_user.get("firm_id")

    if user_role == "firm_admin":
        if not user_firm:
            raise HTTPException(status_code=403, detail="Firm admin has no assigned firm_id.")
        return user_firm

    if user_role == "sys_admin":
        if requested_firm_id:
            return requested_firm_id
        raise HTTPException(status_code=400, detail="firm_id required for sys_admin context.")

    raise HTTPException(status_code=403, detail="Insufficient role permissions.")


@router.get("/by-firm/{firm_id}", response_model=List[StockItemOut], status_code=status.HTTP_200_OK)
async def list_stock_by_firm(
    firm_id: str,
    category: Optional[str] = Query(None, description="Optional category filter"),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    user_role = current_user.get("role")
    user_firm = current_user.get("firm_id")

    if user_role == "firm_admin" and user_firm != firm_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot view stock of another firm.")

    query = {"firm_id": firm_id}
    if category and category.lower() != "all":
        query["category"] = category

    cursor = db.stocks.find(query).sort("category", 1)
    stocks = await cursor.to_list(length=1000)

    # Preload item names
    item_ids = [s["item_id"] for s in stocks]
    items_cursor = db.items.find({"_id": {"$in": item_ids}})
    items_map = {item["_id"]: item.get("item_name", "Unknown") async for item in items_cursor}

    results = []
    for s in stocks:
        entry_dtm = s.get("entry_dtm")
        if isinstance(entry_dtm, datetime):
            entry_dtm = entry_dtm.isoformat()

        udate_dtm = s.get("udate_dtm")
        if isinstance(udate_dtm, datetime):
            udate_dtm = udate_dtm.isoformat()

        results.append({
            "stock_id": str(s["_id"]),
            "item_id": s["item_id"],
            "item_name": items_map.get(s["item_id"], "Unknown Item"),
            "category": s.get("category", "General"),
            "quantity": float(s.get("quantity", 0.0)),
            "unit": s["unit"],
            "warehouse_location": s.get("warehouse_location"),
            "remarks": s.get("remarks"),
            "firm_id": s["firm_id"],
            "entry_dtm": entry_dtm or "",
            "udate_dtm": udate_dtm or "",
        })

    return results


@router.post("/adjust", response_model=StockItemOut, status_code=status.HTTP_200_OK)
async def adjust_stock(
    payload: StockAdjustmentRequest,
    firm_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    target_firm_id = resolve_firm_context(current_user, firm_id)
    user_id = current_user["_id"]
    now_dt = datetime.now(timezone.utc)

    item = await db.items.find_one({"_id": payload.item_id, "firm_id": target_firm_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    stock = await db.stocks.find_one({"firm_id": target_firm_id, "item_id": payload.item_id})

    if stock:
        new_qty = float(stock["quantity"]) + float(payload.quantity_delta)
        if new_qty < 0:
            raise HTTPException(status_code=400, detail="Insufficient stock for deduction.")

        update_fields = {
            "quantity": float(new_qty),
            "udate_dtm": now_dt,
            "user_id": user_id,
        }
        if payload.warehouse_location:
            update_fields["warehouse_location"] = payload.warehouse_location
        if payload.remarks:
            update_fields["remarks"] = payload.remarks

        updated = await db.stocks.find_one_and_update(
            {"_id": stock["_id"]},
            {"$set": update_fields},
            return_document=True,
        )
        stock_doc = updated
    else:
        if payload.quantity_delta < 0:
            raise HTTPException(status_code=400, detail="Cannot initialize stock with negative quantity.")

        stock_id = f"STK_{int(now_dt.timestamp())}_{uuid.uuid4().hex[:4].upper()}"
        stock_doc = {
            "_id": stock_id,
            "stock_id": stock_id,
            "item_id": payload.item_id,
            "category": item.get("category", "General"),
            "quantity": float(payload.quantity_delta),
            "unit": item.get("default_unit", "kg"),
            "warehouse_location": payload.warehouse_location or "Main Store",
            "remarks": payload.remarks,
            "firm_id": target_firm_id,
            "user_id": user_id,
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        }
        await db.stocks.insert_one(stock_doc)

    return {
        "stock_id": str(stock_doc["_id"]),
        "item_id": stock_doc["item_id"],
        "item_name": item.get("item_name", "Unknown Item"),
        "category": stock_doc["category"],
        "quantity": float(stock_doc["quantity"]),
        "unit": stock_doc["unit"],
        "warehouse_location": stock_doc.get("warehouse_location"),
        "remarks": stock_doc.get("remarks"),
        "firm_id": stock_doc["firm_id"],
        "entry_dtm": stock_doc["entry_dtm"].isoformat(),
        "udate_dtm": stock_doc["udate_dtm"].isoformat(),
    }