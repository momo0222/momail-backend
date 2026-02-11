from pydantic import BaseModel

class AgentStats(BaseModel):
    running: bool
    total_emails: int
    processed_emails: int
    pending_actions: int


