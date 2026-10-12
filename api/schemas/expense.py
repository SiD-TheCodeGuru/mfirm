from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field

ExpenseCategoryEnum = Literal[
    "LABOR",
    "ELECTRICITY",
    "WATER",
    "FUEL_FIREWOOD",
    "TRANSPORT",
    "REPAIR_MAINTENANCE",
    "RENT",
    "MISC",
]
PaymentModeEnum = Literal["CASH", "BANK_TRANSFER", "UPI", "CREDIT"]


class ExpenseCreateRequest(BaseModel):
    expense_date: date
    category: ExpenseCategoryEnum
    amount: float = Field(..., gt=0)
    paid_to: Optional[str] = None
    payment_mode: PaymentModeEnum = "CASH"
    remarks: Optional[str] = None


class ExpenseOut(BaseModel):
    expense_id: str
    slno: int
    expense_date: str
    category: str
    amount: float
    paid_to: Optional[str] = None
    payment_mode: str
    remarks: Optional[str] = None
    firm_id: str
    user_id: str
    entry_dtm: str
    udate_dtm: str