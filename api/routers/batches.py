from datetime import datetime, time, timezone
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.core.database import get_database
from api.dependencies import get_current_user
from api.schemas.batch import (
    BatchCreateRequest,
    BatchOut,
    HarvestLogCreateRequest,
    HarvestLogOut,
)

router = APIRouter(prefix="/api/v1/batches", tags=["Batches & Harvest Flushes"])


def resolve_firm_context(current_user: dict, requested_firm_id: Optional[str] = None) -> str:
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


# -------------------------------------------------------------
# 1. CREATE BATCH (Optionally Deduct Spawn/Raw Material Stock)
# -------------------------------------------------------------
@router.post("/create", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
async def create_batch(
    payload: BatchCreateRequest,
    firm_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    target_firm_id = resolve_firm_context(current_user, firm_id)
    user_id = current_user["_id"]
    now_dt = datetime.now(timezone.utc)

    # 1. Prevent duplicate batch codes
    dup = await db.batches.find_one({
        "firm_id": target_firm_id,
        "batch_code": {"$regex": f"^{payload.batch_code.strip()}$", "$options": "i"},
    })
    if dup:
        raise HTTPException(status_code=409, detail=f"Batch code '{payload.batch_code}' already exists.")

    # 2. Validate all consumed items against current stock before making any deductions
    deduction_tasks = []
    consumed_audit_records = []

    for mat in payload.consumed_materials:
        qty_needed = float(mat.quantity)
        if qty_needed <= 0:
            continue

        stock = await db.stocks.find_one({"firm_id": target_firm_id, "item_id": mat.item_id})
        item_master = await db.items.find_one({"_id": mat.item_id, "firm_id": target_firm_id})

        item_name = item_master.get("item_name", "Unknown Item") if item_master else "Unknown Item"
        category = stock.get("category", "General") if stock else "General"
        unit = stock.get("unit", "kg") if stock else "kg"

        if not stock:
            raise HTTPException(
                status_code=404,
                detail=f"Stock record for item '{item_name}' (ID: {mat.item_id}) was not found in stock.",
            )

        current_qty = float(stock.get("quantity", 0.0))
        if current_qty < qty_needed:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{item_name}'. Available: {current_qty} {unit}, Required: {qty_needed} {unit}.",
            )

        deduction_tasks.append((stock["_id"], current_qty - qty_needed))
        consumed_audit_records.append({
            "item_id": mat.item_id,
            "item_name": item_name,
            "category": category,
            "quantity": float(qty_needed),
            "unit": unit,
        })

    # 3. Deduct each consumed item from stocks
    for stock_id, updated_qty in deduction_tasks:
        await db.stocks.update_one(
            {"_id": stock_id},
            {
                "$set": {
                    "quantity": float(updated_qty),
                    "udate_dtm": now_dt,
                    "user_id": user_id,
                }
            },
        )

    # 4. Save batch document
    batch_id = f"BAT_{int(now_dt.timestamp())}_{uuid.uuid4().hex[:4].upper()}"
    spawn_datetime = datetime.combine(payload.spawn_date, time.min).replace(tzinfo=timezone.utc)

    batch_doc = {
        "_id": batch_id,
        "batch_id": batch_id,
        "batch_code": payload.batch_code.strip(),
        "spawn_date": spawn_datetime,
        "room_no": payload.room_no.strip(),
        "bag_count": int(payload.bag_count),
        "dry_substrate_weight_kg": float(payload.dry_substrate_weight_kg),
        "consumed_materials": consumed_audit_records,
        "status": "INCUBATION",
        "total_yield_kg": 0.0,
        "biological_efficiency": 0.0,
        "remarks": payload.remarks.strip() if payload.remarks else None,
        "firm_id": target_firm_id,
        "user_id": user_id,
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }

    await db.batches.insert_one(batch_doc)

    return {
        **batch_doc,
        "spawn_date": payload.spawn_date.isoformat(),
        "entry_dtm": now_dt.isoformat(),
        "udate_dtm": now_dt.isoformat(),
    }


# -------------------------------------------------------------
# 2. LIST BATCHES
# -------------------------------------------------------------
@router.get("/by-firm/{firm_id}", response_model=List[BatchOut], status_code=status.HTTP_200_OK)
async def list_batches_by_firm(
    firm_id: str,
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    user_role = current_user.get("role")
    user_firm = current_user.get("firm_id")

    if user_role == "firm_admin" and user_firm != firm_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot view batches of another firm.")

    cursor = db.batches.find({"firm_id": firm_id}).sort("spawn_date", -1)
    batches = await cursor.to_list(length=500)

    results = []
    for b in batches:
        sp_dt = b.get("spawn_date")
        if isinstance(sp_dt, datetime):
            sp_dt = sp_dt.strftime("%Y-%m-%d")

        results.append({
            "batch_id": str(b["_id"]),
            "batch_code": b["batch_code"],
            "spawn_date": sp_dt or "",
            "room_no": b["room_no"],
            "bag_count": int(b["bag_count"]),
            "dry_substrate_weight_kg": float(b.get("dry_substrate_weight_kg", 0.0)),
            "spawn_item_id": b.get("spawn_item_id"),
            "spawn_qty_used": b.get("spawn_qty_used"),
            "status": b.get("status", "INCUBATION"),
            "total_yield_kg": float(b.get("total_yield_kg", 0.0)),
            "biological_efficiency": float(b.get("biological_efficiency", 0.0)),
            "remarks": b.get("remarks"),
            "firm_id": b["firm_id"],
            "user_id": b["user_id"],
            "entry_dtm": b.get("entry_dtm", datetime.now()).isoformat(),
            "udate_dtm": b.get("udate_dtm", datetime.now()).isoformat(),
        })

    return results


# -------------------------------------------------------------
# 3. LOG DAILY HARVEST (Increments Batch Yield & Stock)
# -------------------------------------------------------------
@router.post("/harvest/log", response_model=HarvestLogOut, status_code=status.HTTP_201_CREATED)
async def log_harvest(
    payload: HarvestLogCreateRequest,
    firm_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    target_firm_id = resolve_firm_context(current_user, firm_id)
    user_id = current_user["_id"]
    now_dt = datetime.now(timezone.utc)

    # 1. Verify Batch
    batch = await db.batches.find_one({"_id": payload.batch_id, "firm_id": target_firm_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Target batch not found.")

    log_id = f"HRV_{int(now_dt.timestamp())}_{uuid.uuid4().hex[:4].upper()}"
    harvest_dt = datetime.combine(payload.harvest_date, time.min).replace(tzinfo=timezone.utc)

    harvest_doc = {
        "_id": log_id,
        "log_id": log_id,
        "batch_id": payload.batch_id,
        "harvest_date": harvest_dt,
        "flush_number": int(payload.flush_number),
        "weight_kg": float(payload.weight_kg),
        "grade": payload.grade,
        "harvested_item_id": payload.harvested_item_id,
        "remarks": payload.remarks.strip() if payload.remarks else None,
        "firm_id": target_firm_id,
        "user_id": user_id,
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }
    await db.harvest_logs.insert_one(harvest_doc)

    # 2. Update Batch Total Yield and Biological Efficiency (B.E. %)
    new_total_yield = float(batch.get("total_yield_kg", 0.0)) + float(payload.weight_kg)
    dry_wt = float(batch.get("dry_substrate_weight_kg", 1.0))
    be_percentage = round((new_total_yield / dry_wt) * 100.0, 2) if dry_wt > 0 else 0.0

    await db.batches.update_one(
        {"_id": payload.batch_id},
        {
            "$set": {
                "total_yield_kg": float(new_total_yield),
                "biological_efficiency": float(be_percentage),
                "status": "FRUITING",
                "udate_dtm": now_dt,
            }
        },
    )

    # 3. Increment Finished Goods Inventory (Fresh Mushrooms) in stocks
    if payload.harvested_item_id:
        fresh_item = await db.items.find_one({"_id": payload.harvested_item_id, "firm_id": target_firm_id})
        fresh_item_category = fresh_item.get("category", "Fresh Mushroom") if fresh_item else "Fresh Mushroom"

        stock_filter = {"firm_id": target_firm_id, "item_id": payload.harvested_item_id}
        existing_stock = await db.stocks.find_one(stock_filter)

        if existing_stock:
            await db.stocks.update_one(
                stock_filter,
                {
                    "$inc": {"quantity": float(payload.weight_kg)},
                    "$set": {"udate_dtm": now_dt, "user_id": user_id},
                },
            )
        else:
            stock_id = f"STK_{int(now_dt.timestamp())}_{uuid.uuid4().hex[:4].upper()}"
            await db.stocks.insert_one({
                "_id": stock_id,
                "stock_id": stock_id,
                "item_id": payload.harvested_item_id,
                "category": fresh_item_category,
                "quantity": float(payload.weight_kg),
                "unit": "kg",
                "warehouse_location": "Cold Room / Harvest Tray",
                "remarks": f"Auto-created from Flush #{payload.flush_number} harvest",
                "firm_id": target_firm_id,
                "user_id": user_id,
                "entry_dtm": now_dt,
                "udate_dtm": now_dt,
            })

    return {
        **harvest_doc,
        "harvest_date": payload.harvest_date.isoformat(),
        "entry_dtm": now_dt.isoformat(),
        "udate_dtm": now_dt.isoformat(),
    }


# -------------------------------------------------------------
# 4. GET HARVEST LOGS FOR A BATCH
# -------------------------------------------------------------
@router.get("/harvest/logs/{batch_id}", response_model=List[HarvestLogOut], status_code=status.HTTP_200_OK)
async def get_batch_harvest_logs(
    batch_id: str,
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    cursor = db.harvest_logs.find({"batch_id": batch_id}).sort("harvest_date", -1)
    logs = await cursor.to_list(length=200)

    results = []
    for log in logs:
        h_dt = log.get("harvest_date")
        if isinstance(h_dt, datetime):
            h_dt = h_dt.strftime("%Y-%m-%d")

        results.append({
            "log_id": str(log["_id"]),
            "batch_id": log["batch_id"],
            "harvest_date": h_dt or "",
            "flush_number": int(log["flush_number"]),
            "weight_kg": float(log["weight_kg"]),
            "grade": log["grade"],
            "harvested_item_id": log.get("harvested_item_id"),
            "remarks": log.get("remarks"),
            "firm_id": log["firm_id"],
            "user_id": log["user_id"],
            "entry_dtm": log.get("entry_dtm", datetime.now()).isoformat(),
            "udate_dtm": log.get("udate_dtm", datetime.now()).isoformat(),
        })

    return results