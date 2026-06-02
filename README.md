# ⚡ Enterprise API Connector Gateway & Bridge

An elegant, production-grade API gateway, aggregator, and normalization layer built with **Python FastAPI**, **SQLAlchemy (SQLite)**, and a high-fidelity **glassmorphic dashboard**. It lets you dynamically register external third-party APIs (for jobs, courses, events), configure headers and parameters, map custom nested structures into unified schemas via a dotted-path normalization engine, and expose secure, cached endpoints.

---

## 🌟 Key Features

1. **Dynamic API Configuration**: Manage and persist connections to any third-party JSON API with custom routing methods, parameters, and headers.
2. **Dotted Path Normalization Engine**: Safe, deep-nested JSON parsing (e.g. mapping `company.name` or `data.listings.0.title`) into standardized schemas.
3. **Unified Standardized Schemas**: Exposes three clean endpoints that return consistent schemas regardless of original data structures:
   - `Jobs`
   - `Courses`
   - `Events`
4. **High-Performance In-Memory Cache**: Automatic caching layer with configurable Time-To-Live (TTL) to avoid third-party rate limits and maintain sub-20ms response times.
5. **Secure Gateway Routing**: Inbound endpoints are protected by cryptographically secure, SHA-256 hashed custom API keys.
6. **Self-contained Mock Servers**: Out-of-the-box local mock endpoints let you test full aggregation, field mappings, and latency tracking instantly.
7. **Premium Glassmorphic Admin Dashboard**: A stunning browser UI to monitor uptime/latency, test connections, manage API keys, and update JSON-based mapping configurations dynamically.

---

## 🏗️ System Architecture

```
                                 +---------------------------------+
                                 |        Client Application       |
                                 +---------------------------------+
                                                 | Secure API Request
                                                 | (with X-API-Key)
                                                 v
                                 +---------------------------------+
                                 |      API CONNECTOR GATEWAY      |
                                 | - Unified Gateway Endpoints     |
                                 | - Dotted-Path Normalizer Engine |
                                 | - In-Memory Cache & Latency Log |
                                 +---------------------------------+
                                           /      |      \
                                          v       v       v
                                     [Job APIs] [Course APIs] [Event APIs]
```

---

## 📂 Project Structure

```
api_connector/
├── main.py              # FastAPI application, gateway routes & mock server endpoints
├── database.py          # SQLite engine and session configuration
├── models.py            # SQLAlchemy models (connections, logs, keys)
├── schemas.py           # Pydantic input/output schemas
├── normalization.py     # JSON dotted path lookup & schema parser
├── seeder.py            # Automatic seeder to populate mock environments
├── requirements.txt     # Python dependency list
├── plan.md              # Project plan & requirements
├── static/              # Dashboard files served by FastAPI
│   ├── index.html       # Glassmorphic single page dashboard
│   ├── css/
│   │   └── style.css    # High-fidelity glassmorphism styles
│   └── js/
│       └── app.js       # SPA dashboard client-side code
└── README.md            # Project documentation (this file)
```

---

## 📊 Standardized Data Models

No matter the format of the external third-party API, the gateway normalizes and maps incoming payloads into these three standardized JSON schemas:

### 💼 Jobs Schema
```json
{
  "id": "string",
  "title": "string",
  "company": "string",
  "location": "string",
  "description": "string",
  "url": "string",
  "salary": "string (optional)",
  "tags": ["string"],
  "posted_at": "string (optional)",
  "source": "string"
}
```

### 🎓 Courses Schema
```json
{
  "id": "string",
  "title": "string",
  "provider": "string",
  "instructor": "string",
  "description": "string",
  "url": "string",
  "price": "string (optional)",
  "duration": "string (optional)",
  "rating": "float (optional)",
  "source": "string"
}
```

### 📅 Events Schema
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

## 🛠️ Installation & Setup

### 1. Prerequisites
- Python 3.8 or higher
- Git

### 2. Clone and Setup Environment
```bash
# Clone the repository
git clone https://github.com/chandan2444/api_connector.git
cd api_connector

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Running the Server
FastAPI automatically initializes the SQLite database and executes the database seed script on the first startup.
```bash
# Run the development server
uvicorn main:app --host 127.0.0.1 --port 8085 --reload
```

Open your browser to:
- **Admin Dashboard**: [http://127.0.0.1:8085](http://127.0.0.1:8085)
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8085/docs](http://127.0.0.1:8085/docs)

---

## 🔑 Default Authentication & Key Management

By default, the seeder registers a developer key. You can pass it in the headers of your HTTP clients.

- **Developer Default Key**: `connector_dev_secret_key_2026`
- **Header Field**: `X-API-Key`

To create additional API keys, use the dashboard's "API Keys" section or make a `POST` request to `/api/v1/keys`. The gateway stores only the cryptographically secure SHA-256 hash of the keys.

---

## 🔌 API Endpoints Reference

### Unified Gateway Endpoints (X-API-Key Protected)

#### 1. Get Unified Jobs
* **Endpoint**: `/api/v1/jobs`
* **Method**: `GET`
* **Headers**: `X-API-Key: <your_api_key>`
* **Sample Request**:
  ```bash
  curl -H "X-API-Key: connector_dev_secret_key_2026" http://127.0.0.1:8085/api/v1/jobs
  ```

#### 2. Get Unified Courses
* **Endpoint**: `/api/v1/courses`
* **Method**: `GET`
* **Headers**: `X-API-Key: <your_api_key>`
* **Sample Request**:
  ```bash
  curl -H "X-API-Key: connector_dev_secret_key_2026" http://127.0.0.1:8085/api/v1/courses
  ```

#### 3. Get Unified Events
* **Endpoint**: `/api/v1/events`
* **Method**: `GET`
* **Headers**: `X-API-Key: <your_api_key>`
* **Sample Request**:
  ```bash
  curl -H "X-API-Key: connector_dev_secret_key_2026" http://127.0.0.1:8085/api/v1/events
  ```

---

### Administrative CRUD Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/connections` | `GET` | List all configured API integrations |
| `/api/v1/connections` | `POST` | Create a new API connection configuration |
| `/api/v1/connections/{id}` | `PUT` | Update an existing API connection |
| `/api/v1/connections/{id}` | `DELETE` | Delete an integration connection |
| `/api/v1/connections/{id}/test` | `POST` | Force fetch & audit response mappings in real-time |
| `/api/v1/keys` | `GET` | List active key labels |
| `/api/v1/keys` | `POST` | Create a new SHA-256 secured API key |
| `/api/v1/keys/{id}` | `DELETE` | Revoke/Delete an API key |
| `/api/v1/analytics` | `GET` | Fetch performance graphs, average latency, and requests count |

---

## ⚙️ Dotted Path JSON Traversal Engine

The core normalization engine supports dynamic nested mappings. If an external API returns a structure with deeply nested elements:

```json
{
  "status": "ok",
  "data": {
    "listings": [
      {
        "job_id": "job-abc",
        "job_title": "AI Architect",
        "organization": {
          "name": "Google DeepMind"
        }
      }
    ]
  }
}
```

You can configure the following in the connection settings:
- **Payload Selector**: `data.listings`
- **Field Mapping JSON**:
  ```json
  {
    "id": "job_id",
    "title": "job_title",
    "company": "organization.name"
  }
  ```

The parser (`normalization.py`) splits keys by the dots, checks whether a nesting level is a dictionary or a list (supporting numeric indices, e.g. `items.0.title`), traverses safely without throwing errors, and resolves `organization.name` to `"Google DeepMind"`.

---

## 💡 Developer Mock Feeds

FastAPI includes built-in mock endpoints that act as third-party APIs. You can inspect or modify their behavior directly inside `main.py`:
- `GET /api/mock/jobs`
- `GET /api/mock/courses`
- `GET /api/mock/events`

These are used by default to show how the normalization engine handles distinct nested lists, pricing parameters, and rating floats out of the box!
