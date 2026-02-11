from pydantic import BaseModel, EmailStr
from typing import Optional, List

class AttachedFile(BaseModel):
    filename: str
    content: str

class GenerateEmailRequest(BaseModel):
    """Advanced version of compose"""
    to: EmailStr
    subject: str
    tone: str
    instructions: str
    attached_files: Optional[List[AttachedFile]] = []
    enable_research: bool = False

class GenerateEmailResponse(BaseModel):
    suggested_reply: str
    research_used: bool
