import time
import json
import httpx
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
import models
import schemas

logger = logging.getLogger("api_connector.normalization")
logging.basicConfig(level=logging.INFO)

def resolve_json_path(data: Any, path: str) -> Any:
    """
    Traverses a nested JSON dictionary/list structure using a dot-separated path.
    Example path: "company.name" or "items.0.title"
    """
    if not path or path == "." or path == "":
        return data

    parts = path.split(".")
    current = data

    for part in parts:
        if current is None:
            return None
        
        # Check if part is a numeric list index
        if isinstance(current, list):
            try:
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            except ValueError:
                # Part is a string key but current is a list. Can't traverse.
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            # Current is a primitive type (str, int, float) but we have more path parts. Can't traverse.
            return None

    return current


async def fetch_and_normalize(connection: models.APIConnection, db: Session) -> List[Dict[str, Any]]:
    """
    Fetches raw data from the configured external API, traverses the payload to locate 
    the target array, applies field mapping configuration, logs metrics, and returns the list of normalized records.
    """
    if not connection.is_active:
        return []

    # Parse headers and query parameters safely
    try:
        headers = json.loads(connection.headers) if connection.headers else {}
    except Exception:
        headers = {}

    try:
        params = json.loads(connection.params) if connection.params else {}
    except Exception:
        params = {}

    try:
        mapping = json.loads(connection.field_mapping) if connection.field_mapping else {}
    except Exception:
        mapping = {}

    start_time = time.time()
    response_status = 500
    status_str = "failure"
    raw_data = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if connection.method.upper() == "POST":
                # For POST, check if we send params as JSON body
                response = await client.post(connection.url, json=params, headers=headers)
            else:
                response = await client.get(connection.url, params=params, headers=headers)
            
            response_status = response.status_code
            response.raise_for_status()
            raw_data = response.json()
            status_str = "success"
    except Exception as e:
        logger.error(f"HTTP fetch failed for API '{connection.name}' ({connection.url}): {e}")
        status_str = "failure"

    # Compute latency
    latency_ms = (time.time() - start_time) * 1000.0

    # Write log record to database asynchronously
    try:
        log_record = models.APILog(
            connection_id=connection.id,
            response_status=response_status,
            response_time_ms=latency_ms,
            status=status_str
        )
        db.add(log_record)
        db.commit()
    except Exception as db_err:
        db.rollback()
        logger.error(f"Failed to save API connection log: {db_err}")

    # Return empty list if fetch failed
    if status_str == "failure" or raw_data is None:
        return []

    # Extract target array of items
    items_raw = resolve_json_path(raw_data, connection.payload_selector)
    if items_raw is None:
        logger.warning(f"Selector '{connection.payload_selector}' returned None for API '{connection.name}'. Defaulting to root payload.")
        items_raw = raw_data

    # If payload is a single object, wrap it in a list
    if isinstance(items_raw, dict):
        items_raw = [items_raw]
    elif not isinstance(items_raw, list):
        logger.error(f"Resolved payload is neither list nor dict: {type(items_raw)}")
        return []

    normalized_items: List[Dict[str, Any]] = []

    for idx, raw_item in enumerate(items_raw):
        if not isinstance(raw_item, dict):
            continue

        normalized_item = {}

        # 1. CATEGORY: JOBS
        if connection.category == "jobs":
            # Mandatory fields: id, title, company, location, description, url, source
            # Optional fields: salary, tags, posted_at

            raw_id = resolve_json_path(raw_item, mapping.get("id", "id"))
            normalized_item["id"] = f"{connection.id}_{raw_id or idx}"
            normalized_item["title"] = str(resolve_json_path(raw_item, mapping.get("title", "title")) or "Untitled Job")
            normalized_item["company"] = str(resolve_json_path(raw_item, mapping.get("company", "company")) or "Unknown Company")
            normalized_item["location"] = str(resolve_json_path(raw_item, mapping.get("location", "location")) or "Remote")
            normalized_item["description"] = str(resolve_json_path(raw_item, mapping.get("description", "description")) or "")
            normalized_item["url"] = str(resolve_json_path(raw_item, mapping.get("url", "url")) or "")
            normalized_item["salary"] = str(resolve_json_path(raw_item, mapping.get("salary", "salary")) or "") if mapping.get("salary") else None
            
            # tags list extraction
            tags_val = resolve_json_path(raw_item, mapping.get("tags", "tags"))
            if isinstance(tags_val, list):
                normalized_item["tags"] = [str(t) for t in tags_val]
            elif isinstance(tags_val, str):
                normalized_item["tags"] = [t.strip() for t in tags_val.split(",") if t.strip()]
            else:
                normalized_item["tags"] = []

            normalized_item["posted_at"] = str(resolve_json_path(raw_item, mapping.get("posted_at", "posted_at")) or "") if mapping.get("posted_at") else None
            normalized_item["source"] = connection.name

        # 2. CATEGORY: COURSES
        elif connection.category == "courses":
            # Mandatory fields: id, title, provider, instructor, description, url, source
            # Optional fields: price, duration, rating

            raw_id = resolve_json_path(raw_item, mapping.get("id", "id"))
            normalized_item["id"] = f"{connection.id}_{raw_id or idx}"
            normalized_item["title"] = str(resolve_json_path(raw_item, mapping.get("title", "title")) or "Untitled Course")
            normalized_item["provider"] = str(resolve_json_path(raw_item, mapping.get("provider", "provider")) or connection.name)
            normalized_item["instructor"] = str(resolve_json_path(raw_item, mapping.get("instructor", "instructor")) or "N/A")
            normalized_item["description"] = str(resolve_json_path(raw_item, mapping.get("description", "description")) or "")
            normalized_item["url"] = str(resolve_json_path(raw_item, mapping.get("url", "url")) or "")
            normalized_item["price"] = str(resolve_json_path(raw_item, mapping.get("price", "price")) or "") if mapping.get("price") else None
            normalized_item["duration"] = str(resolve_json_path(raw_item, mapping.get("duration", "duration")) or "") if mapping.get("duration") else None
            
            rating_val = resolve_json_path(raw_item, mapping.get("rating", "rating"))
            try:
                normalized_item["rating"] = float(rating_val) if rating_val is not None else None
            except Exception:
                normalized_item["rating"] = None

            normalized_item["source"] = connection.name

        # 3. CATEGORY: EVENTS
        elif connection.category == "events":
            # Mandatory fields: id, title, organizer, venue, description, url, date, source
            # Optional fields: price

            raw_id = resolve_json_path(raw_item, mapping.get("id", "id"))
            normalized_item["id"] = f"{connection.id}_{raw_id or idx}"
            normalized_item["title"] = str(resolve_json_path(raw_item, mapping.get("title", "title")) or "Untitled Event")
            normalized_item["organizer"] = str(resolve_json_path(raw_item, mapping.get("organizer", "organizer")) or "Unknown Organizer")
            normalized_item["venue"] = str(resolve_json_path(raw_item, mapping.get("venue", "venue")) or "TBD")
            normalized_item["description"] = str(resolve_json_path(raw_item, mapping.get("description", "description")) or "")
            normalized_item["url"] = str(resolve_json_path(raw_item, mapping.get("url", "url")) or "")
            normalized_item["date"] = str(resolve_json_path(raw_item, mapping.get("date", "date")) or "TBD")
            normalized_item["price"] = str(resolve_json_path(raw_item, mapping.get("price", "price")) or "") if mapping.get("price") else None
            normalized_item["source"] = connection.name

        normalized_items.append(normalized_item)

    return normalized_items
