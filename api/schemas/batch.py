from datetime import date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

BatchStatusEnum = Literal["INCUBATION", "FRUITING", "COMPLETED", "DISCARDED"]
FlushNumberEnum = Literal[1, 2, 3]
GradeEnum = Literal["A_GRADE", "B_GRADE", "COMMERCIAL"]


class ConsumedMaterialIn(BaseModel):
    item_id: str
    quantity: float = Field(..., gt=0)


class ConsumedMaterialOut(BaseModel):
    item_id: str
    item_name: str
    category: str
    quantity: float
    unit: str


class BatchCreateRequest(BaseModel):
    batch_code: str = Field(..., min_length=2, max_length=50)
    spawn_date: date
    room_no: str = Field(..., min_length=1)
    bag_count: int = Field(..., gt=0)
    dry_substrate_weight_kg: float = Field(..., gt=0)
    consumed_materials: List[ConsumedMaterialIn] = Field(default_factory=list)
    remarks: Optional[str] = None


class BatchOut(BaseModel):
    batch_id: str
    batch_code: str
    spawn_date: str
    room_no: str
    bag_count: int
    dry_substrate_weight_kg: float
    consumed_materials: List[ConsumedMaterialOut] = Field(default_factory=list)
    status: str
    total_yield_kg: float
    biological_efficiency: Optional[float] = None
    remarks: Optional[str] = None
    firm_id: str
    user_id: str
    entry_dtm: str
    udate_dtm: str


class HarvestLogCreateRequest(BaseModel):
    batch_id: str
    harvest_date: date
    flush_number: FlushNumberEnum = 1
    weight_kg: float = Field(..., gt=0)
    grade: GradeEnum = "A_GRADE"
    harvested_item_id: Optional[str] = None
    remarks: Optional[str] = None


class HarvestLogOut(BaseModel):
    log_id: str
    batch_id: str
    harvest_date: str
    flush_number: int
    weight_kg: float
    grade: str
    harvested_item_id: Optional[str] = None
    remarks: Optional[str] = None
    firm_id: str
    user_id: str
    entry_dtm: str
    udate_dtm: str