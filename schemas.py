from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Dict, List, Optional, Any
from datetime import datetime

# API Connection Schemas
class APIConnectionBase(BaseModel):
    name: str = Field(..., example="Github Jobs")
    category: str = Field(..., example="jobs")  # "jobs", "courses", "events"
    url: str = Field(..., example="https://jobs.github.com/positions.json")
    method: str = Field("GET", example="GET")
    headers: str = Field("{}", description="JSON string of HTTP headers")
    params: str = Field("{}", description="JSON string of query parameters")
    payload_selector: str = Field("", description="JSONPath dotted selector to list of items")
    field_mapping: str = Field("{}", description="JSON string mapping unified fields to raw fields")
    is_active: bool = True
    cache_ttl: int = Field(300, description="Cache TTL in seconds")

    @validator("category")
    def validate_category(cls, v):
        if v not in ["jobs", "courses", "events"]:
            raise ValueError("Category must be 'jobs', 'courses', or 'events'")
        return v

    @validator("method")
    def validate_method(cls, v):
        if v.upper() not in ["GET", "POST", "PUT"]:
            raise ValueError("Method must be GET, POST, or PUT")
        return v.upper()

class APIConnectionCreate(APIConnectionBase):
    pass

class APIConnectionUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[str] = None
    params: Optional[str] = None
    payload_selector: Optional[str] = None
    field_mapping: Optional[str] = None
    is_active: Optional[bool] = None
    cache_ttl: Optional[int] = None

class APIConnectionRead(APIConnectionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# API Key Schemas
class APIKeyCreate(BaseModel):
    label: str = Field(..., example="Next.js Dashboard App")

class APIKeyRead(BaseModel):
    id: int
    label: str
    key_hash: str
    is_active: bool
    created_at: datetime
    # We only return the raw key on creation, never list it from DB!

    class Config:
        from_attributes = True

# Log Schemas
class APILogRead(BaseModel):
    id: int
    connection_id: int
    timestamp: datetime
    response_status: int
    response_time_ms: float
    status: str

    class Config:
        from_attributes = True

# Unified Object Schemas
class UnifiedJob(BaseModel):
    id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    salary: Optional[str] = None
    tags: List[str] = []
    posted_at: Optional[str] = None
    source: str

class UnifiedCourse(BaseModel):
    id: str
    title: str
    provider: str
    instructor: str
    description: str
    url: str
    price: Optional[str] = None
    duration: Optional[str] = None
    rating: Optional[float] = None
    source: str

class UnifiedEvent(BaseModel):
    id: str
    title: str
    organizer: str
    venue: str
    description: str
    url: str
    date: str
    price: Optional[str] = None
    source: str
