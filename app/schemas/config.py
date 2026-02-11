from pydantic import BaseModel, EmailStr
from typing import List

class AgentConfigBase(BaseModel):
    auto_reply_whitelist: str=""
    auto_reply_blacklist: str="noreply@,no-reply@,donotreply@"
    check_interval: int=60
    dry_run_mode: bool = False
    enable_auto_reply: bool = True
    enable_spam_filter: bool = True
    enable_learning: bool = False

class AgentConfigUpdate(AgentConfigBase):
    """For updating agent config"""
    auto_reply_whitelist: str | None = None
    auto_reply_blacklist: str | None = None
    check_interval: int | None = None
    dry_run_mode: bool | None = None
    enable_auto_reply: bool | None = None
    enable_spam_filter: bool | None = None
    enable_learning: bool | None = None

class AgentConfigResponse(AgentConfigBase):
    """For API responses"""
    id: int
    whitelist_parsed: List[str]
    blacklist_parsed: List[str]

    class COnfig:
        from_attributes = True

class AddEmails(BaseModel):
    emails: List[EmailStr]