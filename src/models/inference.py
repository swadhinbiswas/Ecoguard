from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime, timezone
from src.db.database import Base

class InferenceLog(Base):
    __tablename__ = "inference_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, unique=True, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    input_text = Column(Text, nullable=False)
    prediction_output = Column(Text, nullable=False)
    latency_ms = Column(Float, nullable=False)
    token_count = Column(Integer, nullable=False)
    confidence_score = Column(Float, nullable=True)
    drift_score = Column(Float, nullable=True)
