from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.db import Base


class PlanRecord(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String(255), nullable=True)
    role_title = Column(String(255), nullable=True)
    resume_text = Column(Text, nullable=False)
    jd_text = Column(Text, nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())