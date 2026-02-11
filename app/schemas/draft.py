from pydantic import BaseModel, Field
from datetime import datetime
from typing import List

class DraftCreate(BaseModel):
    to: str = ""
    subject: str = ""
    body: str = ""

class DraftUpdate(BaseModel):
    to: str
    subject: str
    body: str

class DraftResponse(BaseModel):
    id: int
    to: str
    subject: str
    body: str
    attachments: List[dict] = []
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True