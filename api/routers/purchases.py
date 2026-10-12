from datetime import datetime, time, timezone
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.core.database import get_database
from api.dependencies import get_current_user
from api.schemas.purchase import PurchaseCreateRequest, PurchaseOut

router = APIRouter(prefix="/api/v1/purchases", tags=["Purchases & Invoices"])


def resolve_firm_context(current_user: dict, requested_firm_id: Optional[str] = None) -> str:
    user_role = current_user.get("role")
    user_firm = current_user.get("firm_id")

    if user_role == "firm_admin":
        if not user_firm:
            raise HTTPException(status_code=403, detail="User account does not have an assigned firm_id.")
        return user_firm

    if user_role == "sys_admin":
        if requested_firm_id:
            return requested_firm_id
        raise HTTPException(status_code=400, detail="firm_id must be provided for sys_admin context.")

    raise HTTPException(status_code=403, detail="Insufficient role permissions.")


async def get_next_sequence(db, sequence_name: str, firm_id: str) -> int:
    """Atomic counter to ensure BSON int type for sequence numbers."""
    seq = await db.counters.find_one_and_update(
        {"_id": f"{sequence_name}_{firm_id}"},
        {"$inc": {"seq": int(1)}},
        upsert=True,
        return_document=True,
    )
    return int(seq["seq"])


@router.post("/record", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
async def record_purchase(
    payload: PurchaseCreateRequest,
    firm_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    target_firm_id = resolve_firm_context(current_user, firm_id)
    user_id = current_user["_id"]
    now_dt = datetime.now(timezone.utc)

    # 1. Prevent duplicate invoices for the firm
    existing_inv = await db.purchased.find_one({
        "firm_id": target_firm_id,
        "invoice_no": {"$regex": f"^{payload.invoice_no.strip()}$", "$options": "i"},
    })
    if existing_inv:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice #{payload.invoice_no} has already been registered for this firm.",
        )

    # 2. Get master purchase serial number
    purchase_slno = await get_next_sequence(db, "purchase_slno", target_firm_id)
    purchase_id = f"PUR_{int(now_dt.timestamp())}_{uuid.uuid4().hex[:4].upper()}"

    item_docs = []
    embedded_items = []

    # 3. Process line items, create line records, and update stock
    for item_in in payload.items:
        item_master = await db.items.find_one({"_id": item_in.item_id, "firm_id": target_firm_id})
        if not item_master:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with ID '{item_in.item_id}' not found in active firm.",
            )

        item_category = item_master.get("category", "General")
        item_slno = await get_next_sequence(db, "purchased_item_slno", target_firm_id)
        line_item_id = f"PITM_{int(now_dt.timestamp())}_{uuid.uuid4().hex[:4].upper()}"

        # 3A. Purchase item detail record (purchased_items collection)
        doc = {
            "_id": line_item_id,
            "slno": int(item_slno),
            "purchase_slno": int(purchase_slno),
            "invoice_no": payload.invoice_no.strip(),
            "item_id": item_in.item_id,
            "quantity": float(item_in.quantity),
            "unit": item_in.unit,
            "purchage_amt": float(item_in.purchage_amt),
            "remarks": item_in.remarks.strip() if item_in.remarks else None,
            "firm_id": target_firm_id,
            "user_id": user_id,
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        }
        item_docs.append(doc)

        embedded_items.append({
            "item_id": item_in.item_id,
            "item_name": item_master.get("item_name", "Unknown Item"),
            "category": item_category,
            "quantity": float(item_in.quantity),
            "unit": item_in.unit,
            "purchage_amt": float(item_in.purchage_amt),
        })

        # 3B. Upsert stock ledger (stocks collection)
        stock_filter = {"firm_id": target_firm_id, "item_id": item_in.item_id}
        existing_stock = await db.stocks.find_one(stock_filter)

        if existing_stock:
            await db.stocks.update_one(
                stock_filter,
                {
                    "$inc": {"quantity": float(item_in.quantity)},
                    "$set": {
                        "category": item_category,
                        "unit": item_in.unit,
                        "udate_dtm": now_dt,
                        "user_id": user_id,
                    },
                },
            )
        else:
            stock_id = f"STK_{int(now_dt.timestamp())}_{uuid.uuid4().hex[:4].upper()}"
            await db.stocks.insert_one({
                "_id": stock_id,
                "stock_id": stock_id,
                "item_id": item_in.item_id,
                "category": item_category,
                "quantity": float(item_in.quantity),
                "unit": item_in.unit,
                "warehouse_location": "Main Store",
                "remarks": f"Initial stock from Invoice #{payload.invoice_no}",
                "firm_id": target_firm_id,
                "user_id": user_id,
                "entry_dtm": now_dt,
                "udate_dtm": now_dt,
            })

    # 4. Insert all line items into MongoDB
    if item_docs:
        await db.purchased_items.insert_many(item_docs)

    # 5. Insert invoice header into purchased collection
    invoice_datetime = datetime.combine(payload.invoice_date, time.min).replace(tzinfo=timezone.utc)
    purchase_doc = {
        "_id": purchase_id,
        "slno": int(purchase_slno),
        "invoice_no": payload.invoice_no.strip(),
        "invoice_date": invoice_datetime,
        "vendor_name": payload.vendor_name.strip() if payload.vendor_name else None,
        "tax_paid": float(payload.tax_paid),
        "total_paid": float(payload.total_paid),
        "payment_mode": payload.payment_mode,
        "items": embedded_items,
        "remarks": payload.remarks.strip() if payload.remarks else None,
        "firm_id": target_firm_id,
        "user_id": user_id,
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }

    await db.purchased.insert_one(purchase_doc)

    return {
        "purchase_id": purchase_id,
        "slno": purchase_doc["slno"],
        "invoice_no": purchase_doc["invoice_no"],
        "invoice_date": payload.invoice_date.isoformat(),
        "vendor_name": purchase_doc["vendor_name"],
        "tax_paid": purchase_doc["tax_paid"],
        "total_paid": purchase_doc["total_paid"],
        "payment_mode": purchase_doc["payment_mode"],
        "items": purchase_doc["items"],
        "remarks": purchase_doc["remarks"],
        "firm_id": purchase_doc["firm_id"],
        "user_id": purchase_doc["user_id"],
        "entry_dtm": now_dt.isoformat(),
        "udate_dtm": now_dt.isoformat(),
    }


@router.get("/by-firm/{firm_id}", response_model=List[PurchaseOut], status_code=status.HTTP_200_OK)
async def list_purchases_by_firm(
    firm_id: str,
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    user_role = current_user.get("role")
    user_firm = current_user.get("firm_id")

    if user_role == "firm_admin" and user_firm != firm_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot view invoices of another firm.")

    cursor = db.purchased.find({"firm_id": firm_id}).sort("slno", -1)
    purchases = await cursor.to_list(length=500)

    results = []
    for p in purchases:
        inv_dt = p.get("invoice_date")
        if isinstance(inv_dt, datetime):
            inv_dt = inv_dt.strftime("%Y-%m-%d")

        entry_dt = p.get("entry_dtm")
        if isinstance(entry_dt, datetime):
            entry_dt = entry_dt.isoformat()

        udate_dt = p.get("udate_dtm")
        if isinstance(udate_dt, datetime):
            udate_dt = udate_dt.isoformat()

        results.append({
            "purchase_id": str(p["_id"]),
            "slno": p.get("slno", 0),
            "invoice_no": p.get("invoice_no", ""),
            "invoice_date": inv_dt or "",
            "vendor_name": p.get("vendor_name"),
            "tax_paid": float(p.get("tax_paid", 0.0)),
            "total_paid": float(p.get("total_paid", 0.0)),
            "payment_mode": p.get("payment_mode", "CASH"),
            "items": p.get("items", []),
            "remarks": p.get("remarks"),
            "firm_id": p.get("firm_id", ""),
            "user_id": p.get("user_id", ""),
            "entry_dtm": entry_dt or "",
            "udate_dtm": udate_dt or "",
        })

    return results