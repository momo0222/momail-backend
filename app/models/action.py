from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Action(Base):
    """
    Stores actions the agents want to take
    """
    __tablename__ = "actions"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Link to email
    email_id = Column(String, ForeignKey("emails.id"), nullable=False)

    # What action to take
    action_type = Column(String, nullable=False)  # reply, archive, notify, skip
    status = Column(String, index=True, default="pending")  # pending, approved, rejected, executed, failed

    # Reply content (if action is reply)
    suggested_reply = Column(Text, nullable=True)
    actual_reply = Column(Text, nullable=True) # the actual reply sent

    reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    def __repr__(self):
        return f"<Action {self.id}: {self.action_type} ({self.status})>"
