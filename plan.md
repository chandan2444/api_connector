# API Connector System - Project Plan

This document outlines the detailed system architecture, database schema, data aggregation pipeline, normalization engine, and visual dashboard details for the **API Connector**.

---

## 1. System Overview & Architecture

The **API Connector** is a gateway, aggregator, and normalization layer. It is built using **Python FastAPI** and **SQLite** (using SQLAlchemy). It performs the following main functions:
1. **Dynamic API Configuration**: A CRUD database interface where you can register third-party API endpoints (e.g. course APIs, job feeds, event lists), define request headers, authentication, parameters, and custom field-mappings.
2. **Unified Data Schemas**: Defines standardized schemas for `Jobs`, `Courses`, and `Events`.
3. **Payload Normalization & Mapping Engine**: Safely traverses incoming nested JSON structures from arbitrary sources (using dotted paths or selectors) and normalizes them into unified schemas.
4. **Caching Layer**: In-memory caching to minimize latency, avoid external rate-limiting, and speed up client integrations.
5. **Secure Gateway Routing**: Secure, auth-protected endpoints `/api/v1/jobs`, `/api/v1/courses`, and `/api/v1/events` for external client apps, controlled by configurable API Keys.
6. **Premium Glassmorphic Admin Dashboard**: An elegant web UI served directly by FastAPI to manage connections, monitor API uptime/latency, test field-mappings, and manage API keys.

```
       +---------------------------------------------+
       |             Other Applications              |
       +---------------------------------------------+
                              | Secure X-API-Key API call
                              v
       +---------------------------------------------+
       |            API CONNECTOR GATEWAY            |
       |  - Unified Endpoint Routing (/api/v1/...)   |
       |  - Field Mapping & Normalization Engine     |
       |  - Latency Logging & Cache Layer            |
       +---------------------------------------------+
               /              |              \
              v               v               v
       +-------------+ +-------------+ +-------------+
       |   Job APIs  | | Course APIs | | Event APIs  |
       +-------------+ +-------------+ +-------------+
```

---

## 2. Standardized Data Schemas

Regardless of what fields the source API returns, the client will receive clean, standardized models.

### Jobs
```json
{
  "id": "string",
  "title": "string",
  "company": "string",
  "location": "string",
  "description": "string",
  "url": "string (link to original post)",
  "salary": "string (optional)",
  "tags": ["string"],
  "posted_at": "string",
  "source": "string"
}
```

### Courses
```json
{
  "id": "string",
  "title": "string",
  "provider": "string (e.g. Udemy, Coursera)",
  "instructor": "string",
  "description": "string",
  "url": "string",
  "price": "string (optional)",
  "duration": "string (optional)",
  "rating": "float (optional)",
  "source": "string"
}
```

### Events
```json
{
  "id": "string",
  "title": "string",
  "organizer": "string",
  "venue": "string",
  "description": "string",
  "url": "string",
  "date": "string",
  "price": "string (optional)",
  "source": "string"
}
```

---

## 3. Database Schema

We will use SQLite for local persistence with three main tables:

1. **`api_connections`**:
   - `id`: INTEGER (PK)
   - `name`: TEXT (e.g., "Github Jobs")
   - `category`: TEXT ("jobs" | "courses" | "events")
   - `url`: TEXT (HTTP request endpoint)
   - `method`: TEXT ("GET" | "POST")
   - `headers`: TEXT (JSON string of required headers, e.g. authorization bearer)
   - `params`: TEXT (JSON string of query parameters)
   - `payload_selector`: TEXT (JSONPath/dotted selector to find the raw array, e.g., `"results"` or `""` for root)
   - `field_mapping`: TEXT (JSON string representing mapping schema, e.g., `{"title": "job_title", "company": "company.name"}`)
   - `is_active`: BOOLEAN (Quickly enable/disable API aggregator endpoints)
   - `cache_ttl`: INTEGER (Seconds cache is valid)
   - `created_at`: DATETIME

2. **`api_keys`**:
   - `id`: INTEGER (PK)
   - `key_hash`: TEXT (Secured SHA-256 hash of API token)
   - `label`: TEXT (Identifier, e.g., "Main Dashboard App")
   - `is_active`: BOOLEAN
   - `created_at`: DATETIME

3. **`api_logs`**:
   - `id`: INTEGER (PK)
   - `connection_id`: INTEGER (FK)
   - `timestamp`: DATETIME
   - `response_status`: INTEGER (e.g. 200, 404, 500)
   - `response_time_ms`: REAL
   - `status`: TEXT ("success" | "failure")

---

## 4. Key Design Decisions & Features

* **JSON Dotted Path Traversal**: The normalization engine supports nested parsing. For example, if a job API returns `{"company": {"name": "Google", "location": "USA"}}`, you can set the company field mapping to `"company.name"`. The parser will automatically split and resolve this path safely.
* **Unified API Cache**: Integrated in-memory caching will prevent hitting third-party API rate limits and deliver instantaneous loading states (under 20ms) to your frontend app dashboard.
* **API Connection Self-Tester**: Built directly into the dashboard connection manager. When adding an API, you can click "Test Connection" to fetch the live API, input custom mappings, and instantly view the original vs. normalized structures.
* **Seeder Component**: Includes an automated seeder populated with custom mock servers for courses, jobs, and events, allowing you to instantly play with and demonstrate the app out-of-the-box.
* **Vibrant Glassmorphic Interface**: Built with high-fidelity visuals, sleek card designs, micro-interactions, responsive sidebars, custom code highlight themes, and dark/light dynamic styling.

---

## 5. Next Steps

1. **Review & Approve**: Once you are happy with this plan, please reply with your approval.
2. **Build Backend**: I will initialize the FastAPI project, write schemas, models, database configs, and setup the Normalization Engine.
3. **Build UI**: I will construct a premium single-page dashboard with glassmorphism styles and interactive components.
4. **Seed & Run**: I will populate the SQLite database and start the application so you can play with the interface!
