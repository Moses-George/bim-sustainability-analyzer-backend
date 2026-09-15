from app.core.database import Base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from sqlalchemy import  Column, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
import uuid


class BaseModel(Base):
    __abstract__ = True
    
    id = Column(Integer, primary_key=True)
    # id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())