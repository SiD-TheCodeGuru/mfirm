from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

UnitEnum = Literal["ltr", "kg", "packets", "bags", "bottles", "pieces"]

class StockAdjustmentRequest(BaseModel):
    item_id: str
    quantity_delta: float = Field(..., description="Positive for addition, negative for deduction")
    warehouse_location: Optional[str] = None
    remarks: Optional[str] = None

class StockItemOut(BaseModel):
    stock_id: str
    item_id: str
    item_name: str
    category: str
    quantity: float
    unit: str
    warehouse_location: Optional[str] = None
    remarks: Optional[str] = None
    firm_id: str
    entry_dtm: str
    udate_dtm: str