from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class ActionBase(BaseModel):
    """Base action fields"""
    email_id: str
    action_type: str
    reason: Optional[str] = None

class ActionCreate(ActionBase):
    """For creating actions"""
    suggested_reply: Optional[str] = None

class ActionApprove(BaseModel):
    """For approving/editing an action"""
    approved: bool
    edited_reply: Optional[str] = None

class ActionResponse(ActionBase):
    """For API response"""
    id: int
    status: str
    suggested_reply: Optional[str] = None
    actual_reply: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class GenerateReplyRequest(BaseModel):
    email_id: str
    tone: str = "professional"
    custom_instructions: str = ""

class GenerateReplyResponse(BaseModel):
    suggested_reply: str
    email_id: str

