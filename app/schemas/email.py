from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional, List

class EmailBase(BaseModel):
    """Base email fields"""
    subject: str
    from_address: str
    to_address: str
    body: str
    snippet: Optional[str] = None

class EmailCreate(EmailBase):
    """For creating a new email"""
    id: str
    thread_id: str

class EmailResponse(EmailBase):
    """For API response"""
    id: str
    thread_id: Optional[str] = None
    classification: Optional[str] = None
    processed: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class SendReplyRequest(BaseModel):
    email_id: str
    reply_text: str

class AttachmentInfo(BaseModel):
    filepath: str
    original_filename: str

class ComposeEmailRequest(BaseModel):
    to_address: str
    body: str
    subject: str
    attachments: List[AttachmentInfo]=[]
    draft_id: Optional[int] = None
