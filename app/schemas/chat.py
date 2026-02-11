from pydantic import BaseModel
from typing import Optional, List

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    emails: Optional[List[dict]] = None
