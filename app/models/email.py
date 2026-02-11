from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from app.database import Base

class Email(Base):
    """
    Stores emails processed by the agent
    """
    __tablename__ = "emails"

    #Primary Key
    id = Column(String, primary_key=True)

    #Metadata
    thread_id = Column(String, index=True) #indexed for querying
    from_address = Column(String, index=True)
    from_name = Column(String, nullable=True)
    from_raw = Column(String, nullable=True)
    to_address = Column(String)
    subject = Column(Text)
    snippet = Column(Text)
    body = Column(Text)

    #Classification
    classification = Column(String, index=True) #urgent, routine, spam, personal

    #Processing status
    processed = Column(Boolean, default=False, index=True)

    #Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    def __repr__(self):
        return f"<Email {self.id}: {self.subject[:30]}...>"
    
