import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class APIConnection(Base):
    __tablename__ = "api_connections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # "jobs", "courses", "events"
    url = Column(String, nullable=False)
    method = Column(String, default="GET")
    headers = Column(Text, default="{}")  # Stored as JSON string
    params = Column(Text, default="{}")   # Stored as JSON string
    payload_selector = Column(String, default="")  # Dotted JSONPath path, e.g. "results"
    field_mapping = Column(Text, default="{}")     # Stored as JSON string, e.g. {"title": "jobTitle"}
    is_active = Column(Boolean, default=True)
    cache_ttl = Column(Integer, default=300)       # Cache duration in seconds
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    logs = relationship("APILog", back_populates="connection", cascade="all, delete-orphan")


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    label = Column(String, nullable=False)  # Friendly identifier
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class APILog(Base):
    __tablename__ = "api_logs"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("api_connections.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    response_status = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    status = Column(String, nullable=False)  # "success" or "failure"

    connection = relationship("APIConnection", back_populates="logs")
