import json
import hashlib
from sqlalchemy.orm import Session
import models

def seed_db(db: Session):
    # Check if we already have connections seeded
    connection_count = db.query(models.APIConnection).count()
    if connection_count > 0:
        print("Database already has connection records. Skipping seeding.")
        return

    print("Seeding database with default mock connections and developer API key...")

    # 1. Mock Job Connection
    job_connection = models.APIConnection(
        name="Mock Tech Jobs",
        category="jobs",
        url="http://localhost:8085/api/mock/jobs",
        method="GET",
        headers=json.dumps({"Accept": "application/json"}),
        params=json.dumps({}),
        payload_selector="data.listings",
        field_mapping=json.dumps({
            "id": "job_id",
            "title": "job_title",
            "company": "organization.name",
            "location": "work_location",
            "description": "role_description",
            "url": "apply_url",
            "salary": "annual_compensation",
            "tags": "tags_list",
            "posted_at": "date_posted"
        }),
        is_active=True,
        cache_ttl=60
    )

    # 2. Mock Course Connection
    course_connection = models.APIConnection(
        name="Mock eLearning Courses",
        category="courses",
        url="http://localhost:8085/api/mock/courses",
        method="GET",
        headers=json.dumps({"Accept": "application/json"}),
        params=json.dumps({}),
        payload_selector="results",
        field_mapping=json.dumps({
            "id": "id",
            "title": "name",
            "provider": "academy",
            "instructor": "tutor",
            "description": "summary",
            "url": "link",
            "price": "cost",
            "duration": "length",
            "rating": "rating_stars"
        }),
        is_active=True,
        cache_ttl=60
    )

    # 3. Mock Event Connection
    event_connection = models.APIConnection(
        name="Mock Global Tech Events",
        category="events",
        url="http://localhost:8085/api/mock/events",
        method="GET",
        headers=json.dumps({"Accept": "application/json"}),
        params=json.dumps({}),
        payload_selector="",  # Empty represents root level array
        field_mapping=json.dumps({
            "id": "event_code",
            "title": "event_title",
            "organizer": "host_org",
            "venue": "location_name",
            "description": "details",
            "url": "register_link",
            "date": "start_date",
            "price": "ticket_price"
        }),
        is_active=True,
        cache_ttl=60
    )

    db.add(job_connection)
    db.add(course_connection)
    db.add(event_connection)

    # 4. Generate developer API Key
    dev_raw_key = "connector_dev_secret_key_2026"
    key_hash = hashlib.sha256(dev_raw_key.encode("utf-8")).hexdigest()
    
    # Check if key exists
    key_exists = db.query(models.APIKey).filter(models.APIKey.key_hash == key_hash).first()
    if not key_exists:
        dev_key = models.APIKey(
            key_hash=key_hash,
            label="Developer Default Key",
            is_active=True
        )
        db.add(dev_key)

    try:
        db.commit()
        print("Database seeding completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
