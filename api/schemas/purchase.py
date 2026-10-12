from datetime import date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

UnitEnum = Literal["ltr", "kg", "packets", "bags", "bottles", "pieces"]
PaymentModeEnum = Literal["CASH", "BANK_TRANSFER", "UPI", "CREDIT"]


class PurchaseItemIn(BaseModel):
    item_id: str
    quantity: float = Field(..., gt=0)
    unit: UnitEnum
    purchage_amt: float = Field(..., ge=0)
    remarks: Optional[str] = None


class PurchaseItemOut(BaseModel):
    slno: int
    purchase_slno: int
    invoice_no: str
    item_id: str
    item_name: Optional[str] = None
    category: Optional[str] = None
    quantity: float
    unit: str
    purchage_amt: float
    remarks: Optional[str] = None
    firm_id: str
    user_id: str
    entry_dtm: str
    udate_dtm: str


class PurchaseCreateRequest(BaseModel):
    invoice_no: str = Field(..., min_length=1, max_length=50)
    invoice_date: date
    vendor_name: Optional[str] = None
    payment_mode: PaymentModeEnum = "UPI"
    tax_paid: float = Field(0.0, ge=0)
    total_paid: float = Field(..., ge=0)
    remarks: Optional[str] = None
    items: List[PurchaseItemIn] = Field(..., min_items=1)


class PurchaseOut(BaseModel):
    purchase_id: str
    slno: int
    invoice_no: str
    invoice_date: str
    vendor_name: Optional[str] = None
    tax_paid: float
    total_paid: float
    payment_mode: str
    items: List[dict]
    remarks: Optional[str] = None
    firm_id: str
    user_id: str
    entry_dtm: str
    udate_dtm: str