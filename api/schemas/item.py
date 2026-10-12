from typing import Optional
from pydantic import BaseModel, Field


class ItemRegisterRequest(BaseModel):
    item_name: str = Field(..., min_length=3, max_length=100)
    category: str = Field(..., min_length=2, max_length=50)
    default_unit: str = Field(..., min_length=1, max_length=20)
    remarks: Optional[str] = Field(None, max_length=255)


class ItemUpdateRequest(BaseModel):
    item_name: Optional[str] = Field(None, min_length=3, max_length=100)
    category: Optional[str] = Field(None, min_length=2, max_length=50)
    default_unit: Optional[str] = Field(None, min_length=1, max_length=20)
    remarks: Optional[str] = Field(None, max_length=255)


class ItemListOut(BaseModel):
    item_id: str
    item_name: str
    category: str
    default_unit: str
    remarks: Optional[str] = None
    firm_id: str
    user_id: str
    entry_dtm: str
    udate_dtm: Optional[str] = None