from collections import defaultdict
from datetime import datetime, time, timezone
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.core.database import get_database
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/reports", tags=["Farm Analytics & Reports"])


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


@router.get("/summary/{firm_id}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_farm_analytics_summary(
    firm_id: str,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    year: Optional[int] = Query(None, description="e.g. 2026"),
    batch_id: Optional[str] = Query(None, description="Specific Batch ID or 'ALL'"),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    target_firm_id = resolve_firm_context(current_user, firm_id)

    # 1. Build Date Filter Conditions
    date_filter = {}
    if year:
        y_start = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        y_end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        date_filter["$gte"] = y_start
        date_filter["$lte"] = y_end

    if start_date:
        s_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        date_filter["$gte"] = s_dt
    if end_date:
        e_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        date_filter["$lte"] = e_dt

    # 2. Filter Batches
    batch_query = {"firm_id": target_firm_id}
    if batch_id and batch_id != "ALL":
        batch_query["_id"] = batch_id
    elif date_filter:
        batch_query["spawn_date"] = date_filter

    batches = await db.batches.find(batch_query).sort("spawn_date", 1).to_list(length=1000)
    matched_batch_ids = [b["_id"] for b in batches]

    total_bags = sum(b.get("bag_count", 0) for b in batches)
    total_substrate_kg = sum(float(b.get("dry_substrate_weight_kg", 0.0)) for b in batches)
    total_yield_kg = sum(float(b.get("total_yield_kg", 0.0)) for b in batches)

    avg_be = round((total_yield_kg / total_substrate_kg) * 100.0, 2) if total_substrate_kg > 0 else 0.0

    batch_be_data = [
        {
            "code": b.get("batch_code", "N/A"),
            "be": round(float(b.get("biological_efficiency", 0.0)), 1),
            "yield_kg": round(float(b.get("total_yield_kg", 0.0)), 2),
            "bags": b.get("bag_count", 0),
        }
        for b in batches[-15:]
    ]

    # 3. Filter Harvest Logs
    harvest_query = {"firm_id": target_firm_id}
    if batch_id and batch_id != "ALL":
        harvest_query["batch_id"] = batch_id
    elif matched_batch_ids:
        harvest_query["batch_id"] = {"$in": matched_batch_ids}

    if date_filter:
        harvest_query["harvest_date"] = date_filter

    harvest_logs = await db.harvest_logs.find(harvest_query).sort("harvest_date", 1).to_list(length=3000)

    flush_distribution = {1: 0.0, 2: 0.0, 3: 0.0}
    daily_yield_map = defaultdict(float)

    for h in harvest_logs:
        wt = float(h.get("weight_kg", 0.0))
        fl = int(h.get("flush_number", 1))
        if fl in flush_distribution:
            flush_distribution[fl] += wt

        h_dt = h.get("harvest_date")
        if isinstance(h_dt, datetime):
            daily_yield_map[h_dt.strftime("%Y-%m-%d")] += wt

    daily_timeline = sorted(
        [{"date": dt, "weight": round(wt, 2)} for dt, wt in daily_yield_map.items()],
        key=lambda x: x["date"],
    )

    # 4. Filter Expenses
    expense_query = {"firm_id": target_firm_id}
    if date_filter:
        expense_query["expense_date"] = date_filter

    expenses = await db.expenses.find(expense_query).to_list(length=2000)
    expense_category_map = defaultdict(float)
    total_operating_expense = 0.0

    for exp in expenses:
        amt = float(exp.get("amount", 0.0))
        cat = exp.get("category", "MISC")
        expense_category_map[cat] += amt
        total_operating_expense += amt

    # 5. Filter Purchases
    purchase_query = {"firm_id": target_firm_id}
    if date_filter:
        purchase_query["invoice_date"] = date_filter

    purchases = await db.purchased.find(purchase_query).to_list(length=1000)
    total_purchase_cost = sum(float(p.get("total_paid", 0.0)) for p in purchases)

    # 6. Economics
    filtered_harvest_sum = sum(h["weight"] for h in daily_timeline)
    effective_yield = filtered_harvest_sum if filtered_harvest_sum > 0 else total_yield_kg
    cost_per_kg = (
        round((total_operating_expense + total_purchase_cost) / effective_yield, 2)
        if effective_yield > 0
        else 0.0
    )

    return {
        "kpis": {
            "total_batches": len(batches),
            "total_bags_spawned": total_bags,
            "total_yield_kg": round(effective_yield, 2),
            "average_be_percent": avg_be,
            "total_expenses": round(total_operating_expense, 2),
            "total_purchases": round(total_purchase_cost, 2),
            "cost_per_kg": cost_per_kg,
        },
        "batch_be_data": batch_be_data,
        "flush_distribution": {
            "Flush 1 (Primary)": round(flush_distribution[1], 2),
            "Flush 2 (Secondary)": round(flush_distribution[2], 2),
            "Flush 3 (Final)": round(flush_distribution[3], 2),
        },
        "daily_timeline": daily_timeline[-30:],
        "expense_breakdown": {k: round(v, 2) for k, v in expense_category_map.items()},
    }