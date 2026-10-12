from datetime import datetime, time, timezone
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.core.database import get_database
from api.dependencies import get_current_user
from api.schemas.expense import ExpenseCreateRequest, ExpenseOut

router = APIRouter(prefix="/api/v1/expenses", tags=["Operational Expenses & Labor"])


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


async def get_next_sequence(db, sequence_name: str, firm_id: str) -> int:
    seq = await db.counters.find_one_and_update(
        {"_id": f"{sequence_name}_{firm_id}"},
        {"$inc": {"seq": int(1)}},
        upsert=True,
        return_document=True,
    )
    return int(seq["seq"])


@router.post("/record", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def record_expense(
    payload: ExpenseCreateRequest,
    firm_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    target_firm_id = resolve_firm_context(current_user, firm_id)
    user_id = current_user["_id"]
    now_dt = datetime.now(timezone.utc)

    slno = await get_next_sequence(db, "expense_slno", target_firm_id)
    expense_id = f"EXP_{int(now_dt.timestamp())}_{uuid.uuid4().hex[:4].upper()}"
    exp_date_dt = datetime.combine(payload.expense_date, time.min).replace(tzinfo=timezone.utc)

    expense_doc = {
        "_id": expense_id,
        "expense_id": expense_id,
        "slno": int(slno),
        "expense_date": exp_date_dt,
        "category": payload.category,
        "amount": float(payload.amount),
        "paid_to": payload.paid_to.strip() if payload.paid_to else None,
        "payment_mode": payload.payment_mode,
        "remarks": payload.remarks.strip() if payload.remarks else None,
        "firm_id": target_firm_id,
        "user_id": user_id,
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }

    await db.expenses.insert_one(expense_doc)

    return {
        **expense_doc,
        "expense_date": payload.expense_date.isoformat(),
        "entry_dtm": now_dt.isoformat(),
        "udate_dtm": now_dt.isoformat(),
    }


@router.get("/by-firm/{firm_id}", response_model=List[ExpenseOut], status_code=status.HTTP_200_OK)
async def list_expenses_by_firm(
    firm_id: str,
    category: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    user_role = current_user.get("role")
    user_firm = current_user.get("firm_id")

    if user_role == "firm_admin" and user_firm != firm_id:
        raise HTTPException(status_code=403, detail="Forbidden to view expenses of another firm.")

    query = {"firm_id": firm_id}
    if category and category != "ALL":
        query["category"] = category

    cursor = db.expenses.find(query).sort("expense_date", -1)
    expenses = await cursor.to_list(length=1000)

    results = []
    for exp in expenses:
        exp_dt = exp.get("expense_date")
        if isinstance(exp_dt, datetime):
            exp_dt = exp_dt.strftime("%Y-%m-%d")

        entry_dt = exp.get("entry_dtm")
        if isinstance(entry_dt, datetime):
            entry_dt = entry_dt.isoformat()

        udate_dt = exp.get("udate_dtm")
        if isinstance(udate_dt, datetime):
            udate_dt = udate_dt.isoformat()

        results.append({
            "expense_id": str(exp["_id"]),
            "slno": int(exp.get("slno", 0)),
            "expense_date": exp_dt or "",
            "category": exp.get("category", "MISC"),
            "amount": float(exp.get("amount", 0.0)),
            "paid_to": exp.get("paid_to"),
            "payment_mode": exp.get("payment_mode", "CASH"),
            "remarks": exp.get("remarks"),
            "firm_id": exp.get("firm_id", ""),
            "user_id": exp.get("user_id", ""),
            "entry_dtm": entry_dt or "",
            "udate_dtm": udate_dt or "",
        })

    return results