from pydantic import BaseModel
from typing import List

class BulkEmailIds(BaseModel):
    """Schema for bulk email IDs."""
    email_ids: List[str]

class MarkReadRequest(BulkEmailIds):
    """Schema for marking emails as read."""
    execute_in_gmail: bool = True

class BulkDeleteRequest(BulkEmailIds):
    """Schema for bulk deleting emails."""
    delete_from_gmail: bool = False

class BulkDeleteSenderRequest(BaseModel):
    """Bulk delete all emails from a sender"""
    sender: str
    delete_from_gmail: bool = False

class ArchiveSenderRequest(BaseModel):
    """Archive all emails from a sender"""
    sender: str
    execute_in_gmail: bool = False

class ExecutePendingRequest(BaseModel):
    """Execute pending actions"""
    action_type: str | None = None