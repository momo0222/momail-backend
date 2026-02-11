from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.sql import func
from app.database import Base

class AgentConfig(Base):
    """
    Stores agent configuration (whitelist, blacklist, settings)
    Single row table - only one config exists
    """
    __tablename__ = "agent_config"

    id = Column(Integer, primary_key=True, default=1)

    # Whitelist/Blacklist (comma separated)
    auto_reply_whitelist = Column(Text, default="")
    auto_reply_blacklist = Column(Text, default="noreply@,no-reply@,donotreply@")

    # Agent settings
    check_interval = Column(Integer, default=60)  # in seconds
    dry_run_mode = Column(Boolean, default=False)  # if True, agent won't send emails

    # Feature flags
    enable_auto_reply = Column(Boolean, default=True)
    enable_spam_filter = Column(Boolean, default=True)
    enable_learning = Column(Boolean, default=False)

    def get_whitelist(self) -> list:
        """Parse whitelist into list"""
        if not self.auto_reply_whitelist: # type: ignore
            return []
        return [email.strip().lower() for email in self.auto_reply_whitelist.split(",") if email.strip()]
    
    def get_blacklist(self) -> list:
        """Parse blacklist into list"""
        if not self.auto_reply_blacklist: # type: ignore
            return []
        return [email.strip().lower() for email in self.auto_reply_blacklist.split(",") if email.strip()]