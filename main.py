import os
import time
import json
import secrets
import hashlib
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, Header, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import database
import models
import schemas
import normalization
from seeder import seed_db

# Create database tables if they do not exist
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="API Connector Gateway & Bridge",
    description="Unified API aggregator and data normalization manager.",
    version="1.0.0"
)

# CORS middleware config to allow other apps dashboard integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup Seeding Hook
@app.on_event("startup")
def startup_event():
    db = next(database.get_db())
    try:
        seed_db(db)
    finally:
        db.close()


# =====================================================================
# IN-MEMORY CACHE MANAGER
# =====================================================================
class MemoryCache:
    def __init__(self):
        # Format: { connection_id: {"timestamp": float, "data": List[Dict]} }
        self._cache: Dict[int, Dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, connection_id: int, ttl_seconds: int) -> Optional[List[Dict[str, Any]]]:
        if connection_id not in self._cache:
            self.misses += 1
            return None
        
        cached = self._cache[connection_id]
        if time.time() - cached["timestamp"] > ttl_seconds:
            self.misses += 1
            # Expired
            del self._cache[connection_id]
            return None
        
        self.hits += 1
        return cached["data"]

    def set(self, connection_id: int, data: List[Dict[str, Any]]):
        self._cache[connection_id] = {
            "timestamp": time.time(),
            "data": data
        }

    def clear(self):
        self._cache.clear()
        self.hits = 0
        self.misses = 0

cache_manager = MemoryCache()


# =====================================================================
# SECURITY DEPENDENCY
# =====================================================================
def verify_api_key(x_api_key: Optional[str] = Header(None), db: Session = Depends(database.get_db)):
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Please provide 'X-API-Key' in headers."
        )
    
    key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
    api_key = db.query(models.APIKey).filter(
        models.APIKey.key_hash == key_hash,
        models.APIKey.is_active == True
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key."
        )
    
    return api_key


# =====================================================================
# API CONNECTION CRUD ENDPOINTS
# =====================================================================
@app.get("/api/v1/connections", response_model=List[schemas.APIConnectionRead])
def list_connections(db: Session = Depends(database.get_db)):
    return db.query(models.APIConnection).all()

@app.get("/api/v1/connections/{id}", response_model=schemas.APIConnectionRead)
def get_connection(id: int, db: Session = Depends(database.get_db)):
    connection = db.query(models.APIConnection).filter(models.APIConnection.id == id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection

@app.post("/api/v1/connections", response_model=schemas.APIConnectionRead)
def create_connection(connection_in: schemas.APIConnectionCreate, db: Session = Depends(database.get_db)):
    # Verify field mappings and selectors can be formatted
    try:
        json.loads(connection_in.headers)
        json.loads(connection_in.params)
        json.loads(connection_in.field_mapping)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Headers, params, and field_mappings must be valid JSON strings: {e}")

    new_conn = models.APIConnection(**connection_in.dict())
    db.add(new_conn)
    try:
        db.commit()
        db.refresh(new_conn)
        return new_conn
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.put("/api/v1/connections/{id}", response_model=schemas.APIConnectionRead)
def update_connection(id: int, connection_in: schemas.APIConnectionUpdate, db: Session = Depends(database.get_db)):
    connection = db.query(models.APIConnection).filter(models.APIConnection.id == id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    update_data = connection_in.dict(exclude_unset=True)

    # Validate JSON formats if provided
    for field in ["headers", "params", "field_mapping"]:
        if field in update_data and update_data[field] is not None:
            try:
                json.loads(update_data[field])
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Field '{field}' must be a valid JSON string: {e}")

    for field, value in update_data.items():
        setattr(connection, field, value)

    try:
        db.commit()
        db.refresh(connection)
        # Invalidate cache for this connection
        if connection.id in cache_manager._cache:
            del cache_manager._cache[connection.id]
        return connection
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.delete("/api/v1/connections/{id}")
def delete_connection(id: int, db: Session = Depends(database.get_db)):
    connection = db.query(models.APIConnection).filter(models.APIConnection.id == id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    db.delete(connection)
    try:
        db.commit()
        # Invalidate cache
        if id in cache_manager._cache:
            del cache_manager._cache[id]
        return {"status": "success", "message": f"Connection '{connection.name}' deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# Live Test Route: Normalizes data on-the-fly for custom parameter auditing
@app.post("/api/v1/connections/{id}/test")
async def test_connection(id: int, db: Session = Depends(database.get_db)):
    connection = db.query(models.APIConnection).filter(models.APIConnection.id == id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Force a direct, bypass-cache HTTP request
    start_time = time.time()
    try:
        normalized_data = await normalization.fetch_and_normalize(connection, db)
        latency_ms = (time.time() - start_time) * 1000.0

        # Retrieve the latest raw data block to show user what we matched
        headers = json.loads(connection.headers) if connection.headers else {}
        params = json.loads(connection.params) if connection.params else {}
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            if connection.method.upper() == "POST":
                res = await client.post(connection.url, json=params, headers=headers)
            else:
                res = await client.get(connection.url, params=params, headers=headers)
            raw_payload = res.json()

        return {
            "status": "success",
            "latency_ms": latency_ms,
            "items_count": len(normalized_data),
            "raw_payload_preview": raw_payload,
            "normalized_data_preview": normalized_data
        }
    except Exception as e:
        return {
            "status": "failure",
            "error_message": str(e)
        }


# =====================================================================
# API KEY MANAGEMENT ENDPOINTS
# =====================================================================
@app.get("/api/v1/keys", response_model=List[schemas.APIKeyRead])
def list_keys(db: Session = Depends(database.get_db)):
    return db.query(models.APIKey).all()

@app.post("/api/v1/keys")
def create_key(key_in: schemas.APIKeyCreate, db: Session = Depends(database.get_db)):
    # Generate 32 bytes cryptographically secure key
    raw_key = f"connector_key_{secrets.token_hex(16)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    new_key = models.APIKey(
        key_hash=key_hash,
        label=key_in.label,
        is_active=True
    )
    db.add(new_key)
    try:
        db.commit()
        db.refresh(new_key)
        # Return raw_key here ONLY ONCE so user can copy it!
        return {
            "id": new_key.id,
            "label": new_key.label,
            "is_active": new_key.is_active,
            "created_at": new_key.created_at,
            "raw_api_key": raw_key
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.delete("/api/v1/keys/{id}")
def delete_key(id: int, db: Session = Depends(database.get_db)):
    api_key = db.query(models.APIKey).filter(models.APIKey.id == id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")

    db.delete(api_key)
    try:
        db.commit()
        return {"status": "success", "message": "API key successfully revoked."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


# =====================================================================
# UNIFIED GATEWAYS (SECURE GATEWAY ENDPOINTS)
# =====================================================================
async def aggregate_category(category: str, db: Session) -> List[Dict[str, Any]]:
    # 1. Fetch active connections
    connections = db.query(models.APIConnection).filter(
        models.APIConnection.category == category,
        models.APIConnection.is_active == True
    ).all()

    tasks = []
    
    for conn in connections:
        # Check cache manager
        cached_data = cache_manager.get(conn.id, conn.cache_ttl)
        if cached_data is not None:
            # Add tasks that return cached values instantly to gather
            async def get_cached(data=cached_data):
                return data
            tasks.append(get_cached())
        else:
            # Not in cache, create fetch and normalize task
            async def fetch_and_cache(connection=conn):
                items = await normalization.fetch_and_normalize(connection, db)
                cache_manager.set(connection.id, items)
                return items
            tasks.append(fetch_and_cache())

    if not tasks:
        return []

    # Run in parallel
    results_nested = await asyncio.gather(*tasks)
    
    # Flatten list
    aggregated = []
    for item_list in results_nested:
        aggregated.extend(item_list)

    return aggregated

@app.get("/api/v1/jobs", response_model=List[schemas.UnifiedJob])
async def get_unified_jobs(
    db: Session = Depends(database.get_db), 
    api_key: models.APIKey = Depends(verify_api_key)
):
    return await aggregate_category("jobs", db)

@app.get("/api/v1/courses", response_model=List[schemas.UnifiedCourse])
async def get_unified_courses(
    db: Session = Depends(database.get_db), 
    api_key: models.APIKey = Depends(verify_api_key)
):
    return await aggregate_category("courses", db)

@app.get("/api/v1/events", response_model=List[schemas.UnifiedEvent])
async def get_unified_events(
    db: Session = Depends(database.get_db), 
    api_key: models.APIKey = Depends(verify_api_key)
):
    return await aggregate_category("events", db)


# =====================================================================
# ANALYTICS & MONITORING ROUTE
# =====================================================================
@app.get("/api/v1/analytics")
def get_analytics(db: Session = Depends(database.get_db)):
    connections = db.query(models.APIConnection).all()
    logs = db.query(models.APILog).order_by(models.APILog.timestamp.desc()).limit(100).all()

    # Latency logs and status summary
    latency_summary = {}
    active_count = 0
    inactive_count = 0

    for c in connections:
        if c.is_active:
            active_count += 1
        else:
            inactive_count += 1

        # Calculate average latency of this connection from its logs
        c_logs = db.query(models.APILog).filter(models.APILog.connection_id == c.id).all()
        avg_lat = sum(l.response_time_ms for l in c_logs) / len(c_logs) if c_logs else 0
        latency_summary[c.name] = {
            "avg_latency_ms": round(avg_lat, 2),
            "requests_count": len(c_logs),
            "success_rate": round(sum(1 for l in c_logs if l.status == "success") / len(c_logs) * 100, 1) if c_logs else 100.0,
            "category": c.category
        }

    # Format log entries for visual graph feeds
    formatted_logs = []
    for log in logs:
        conn = next((c for c in connections if c.id == log.connection_id), None)
        formatted_logs.append({
            "id": log.id,
            "connection_name": conn.name if conn else "Unknown Source",
            "timestamp": log.timestamp.isoformat(),
            "response_status": log.response_status,
            "response_time_ms": round(log.response_time_ms, 2),
            "status": log.status
        })

    return {
        "connections_summary": {
            "total": len(connections),
            "active": active_count,
            "inactive": inactive_count
        },
        "cache": {
            "hits": cache_manager.hits,
            "misses": cache_manager.misses,
            "total_queries": cache_manager.hits + cache_manager.misses
        },
        "performance": latency_summary,
        "recent_logs": formatted_logs
    }


# =====================================================================
# LOCAL MOCK FEEDS
# =====================================================================
@app.get("/api/mock/jobs")
def mock_jobs_endpoint():
    return {
        "status": "success",
        "count": 3,
        "data": {
            "listings": [
                {
                    "job_id": "job-101",
                    "job_title": "Senior AI Research Engineer",
                    "organization": {
                        "name": "AIAxis Labs",
                        "hq": "San Francisco, CA"
                    },
                    "work_location": "Hybrid (SF or Remote)",
                    "role_description": "We are seeking a senior engineer to work on advanced agentic capabilities including tool orchestration and planning models.",
                    "apply_url": "https://aiaxis.example.com/careers/job-101",
                    "annual_compensation": "$180,000 - $240,000",
                    "tags_list": ["AI", "Python", "FastAPI", "PyTorch"],
                    "date_posted": "2026-05-30"
                },
                {
                    "job_id": "job-102",
                    "job_title": "Lead Full-Stack Web Architect",
                    "organization": {
                        "name": "VibrantUI Studios",
                        "hq": "New York, NY"
                    },
                    "work_location": "Remote",
                    "role_description": "Join our design-focused team to craft gorgeous, highly responsive, glassmorphic dashboards using vanilla CSS and modern JS integrations.",
                    "apply_url": "https://vibrantui.example.com/jobs/102",
                    "annual_compensation": "$140,000 - $175,000",
                    "tags_list": ["Vanilla CSS", "JavaScript", "HTML5", "UX"],
                    "date_posted": "2026-05-28"
                },
                {
                    "job_id": "job-103",
                    "job_title": "Senior Systems Engineer",
                    "organization": {
                        "name": "CloudScale Platforms",
                        "hq": "Seattle, WA"
                    },
                    "work_location": "On-site (Seattle)",
                    "role_description": "Help design and implement next-generation highly-available server clustering configurations.",
                    "apply_url": "https://cloudscale.example.com/careers/sys-3",
                    "annual_compensation": "$160,000 - $200,000",
                    "tags_list": ["Go", "Linux", "Docker", "Kubernetes"],
                    "date_posted": "2026-05-25"
                }
            ]
        }
    }


@app.get("/api/mock/courses")
def mock_courses_endpoint():
    return {
        "status_code": 200,
        "results": [
            {
                "id": "course-c1",
                "name": "Advanced Agentic AI Development",
                "academy": "AIAxis Academy",
                "tutor": "Dr. Antigravity",
                "summary": "Master the art of building autonomous, self-healing, planning-mode coding agents that interact with files and terminal sessions.",
                "link": "https://aiaxis.example.com/courses/c1",
                "cost": "$49.99",
                "length": "12 hours",
                "rating_stars": 4.96
            },
            {
                "id": "course-c2",
                "name": "CSS Glassmorphism & High-Fidelity UI Design",
                "academy": "CreativeWeb School",
                "tutor": "Sarah Glass",
                "summary": "Learn modern styling techniques like backdrop-filters, custom properties, and glowing shadows to create premium state-of-the-art designs.",
                "link": "https://creativeweb.example.com/css-glassmorphism",
                "cost": "Free",
                "length": "4.5 hours",
                "rating_stars": 4.78
            },
            {
                "id": "course-c3",
                "name": "FastAPI Masterclass: Building Microservices",
                "academy": "CodeCraft Labs",
                "tutor": "Alex Starlette",
                "summary": "Step-by-step masterclass on deploying highly performance FastAPI microservices complete with background workers and custom middlewares.",
                "link": "https://codecraft.example.com/fastapi-mastery",
                "cost": "$19.99",
                "length": "8.5 hours",
                "rating_stars": 4.88
            }
        ]
    }


@app.get("/api/mock/events")
def mock_events_endpoint():
    return [
        {
            "event_code": "evt-201",
            "event_title": "Global AI Agents Summit 2026",
            "host_org": "AI Pioneers Association",
            "location_name": "Moscone Center, SF & Virtual",
            "details": "The premier gathering for developers, researchers, and tech architects working in agentic architectures.",
            "register_link": "https://summit.example.com/2026",
            "start_date": "2026-09-15",
            "ticket_price": "$199.00"
        },
        {
            "event_code": "evt-202",
            "event_title": "Web Aesthetics & Styling Workshop",
            "host_org": "Designers Code Collective",
            "location_name": "Online (Zoom)",
            "details": "An interactive, hands-on workshop focused on creating high-end, premium web layouts that amaze users on first sight.",
            "register_link": "https://workshop.example.com/aesthetics",
            "start_date": "2026-06-25",
            "ticket_price": "Free"
        },
        {
            "event_code": "evt-203",
            "event_title": "Open Source Tech Meetup",
            "host_org": "Local Tech Community",
            "location_name": "AIAxis Headquarters, Austin",
            "details": "Come share your side-projects, pair program, and talk about the latest technologies in the open-source ecosystem.",
            "register_link": "https://meetup.example.com/austin-os",
            "start_date": "2026-06-18",
            "ticket_price": "Free"
        }
    ]


# =====================================================================
# SERVING WEB DASHBOARD AS STATIC RESOURCES
# =====================================================================
# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

# Route root to serve the SPA index file
@app.get("/")
def read_root():
    return FileResponse("static/index.html")

# Mount the static assets directory at /static
app.mount("/static", StaticFiles(directory="static"), name="static")
