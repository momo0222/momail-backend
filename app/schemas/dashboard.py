from pydantic import BaseModel
from typing import Dict, List

class Totals(BaseModel):
    emails: int
    processed: int
    pending_actions: int
    unprocessed: int

class RecentActivity(BaseModel):
    last_7_days: int

class TopSender(BaseModel):
    email: str
    count: int

class DashboardStats(BaseModel):
    totals: Totals
    classification: Dict[str, int]
    action_types: Dict[str, int]
    recent_activity: RecentActivity
    top_senders: List[TopSender]