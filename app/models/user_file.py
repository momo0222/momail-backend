from sqlalchemy import Column, Integer, String, DateTime, BigInteger
from datetime import datetime
from sqlalchemy import func
from app.database import Base

class UserFile(Base):
    """Persistent user files (resumes, templates, etc)"""
    __tablename__ = "user_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    size = Column(BigInteger)
    file_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())