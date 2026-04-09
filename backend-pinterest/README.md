# Pinterest Clone Backend

A robust, asynchronous backend for a Pinterest-like application, built with **FastAPI**. It features a modern Python stack and integrates with several services, including PostgreSQL, Redis, RabbitMQ, MinIO, and Celery, to provide scalable data storage, caching, media handling, and background task processing.

## 🚀 Key Features

* **FastAPI** based robust API structure (async processing).
* **PostgreSQL + SQLAlchemy + asyncpg** for relational data mapping and migrations (Alembic).
* **MinIO (AWS S3 Compatible)** integration for media/image uploads and storage via `aioboto3`.
* **Redis** caching and rate limiting (using `slowapi`).
* **RabbitMQ & Celery** for executing background jobs and scheduled tasks.
* **JWT Authentication** and password hashing.
* **Machine Learning Integration** using `PyTorch`, `Transformers`, and `Clarifai`.

## 🛠️ Tech Stack

- **Framework:** FastAPI, Uvicorn
- **Language:** Python 3.12+ (managed with `uv`)
- **Database:** PostgreSQL (PostgreSQL 16)
- **Caching & Rate Limiting:** Redis
- **Message Broker:** RabbitMQ
- **Background Tasks:** Celery
- **Object Storage:** MinIO
- **ORM & Migrations:** SQLAlchemy 2.0+, Alembic
- **Testing:** Pytest, pytest-asyncio
- **Linter & Formatter:** Ruff

## ⚙️ Prerequisites

To run this project you will need:
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- (Optional) [uv](https://github.com/astral-sh/uv) or Python 3.12+ if running locally outside of Docker.

## 🐳 Running with Docker (Recommended)

The easiest way to get the entire stack running is via `docker-compose`.

1. **Clone the repository and jump into the backend directory:**
```bash
cd backend-pinterest
```

2. **Configure Environment Variables:**
Copy the example environment variables or create a `.env` file based on `.env.example` in the root of the backend directory.
```bash
# Example essential variables:
DB_USER=postgres
DB_PASSWORD=secret
DB_NAME=pinterest
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=pinterest-images
```

3. **Spin up the containers:**
```bash
docker compose up --build -d
```
This command starts:
- The FastAPI application (`api`) accessible at http://localhost:8000
- PostgreSQL Database (`db`) accessible at port 5432
- MinIO Object Storage (`minio`) accessible at http://localhost:9000 (Console at 9001)
- Redis (`redis`) accessible at port 6379 
- RabbitMQ (`rabbitmq`) accessible at port 5672 (Management UI at 15672)
- Celery worker & Celery beat

4. **Apply Database Migrations:**
Ensure your database schema is up-to-date:
```bash
docker compose exec api alembic upgrade head
```

5. **Access the API:**
* Interactive API Docs (Swagger): http://localhost:8000/docs
* ReDoc UI: http://localhost:8000/redoc

## 💻 Running Locally (Development)

If you prefer to run the FastAPI app on your host machine while keeping databases in Docker:

1. **Start infrastructure via Docker:**
```bash
docker compose up -d db redis rabbitmq minio minio-init
```

2. **Install dependencies using uv (or pip):**
```bash
uv sync # or pip install -r pyproject.toml
```

3. **Run Alembic Migrations:**
```bash
alembic upgrade head
```

4. **Start the API Server:**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## 📂 Project Structure
```
backend-pinterest/
├── alembic.ini             # Alembic migration config
├── docker-compose.yaml     # Local Docker infrastructure setup
├── Dockerfile              # App container image spec
├── migrations/             # Alembic revision files
├── pyproject.toml          # Project dependencies and configurations
├── src/                    # Main application code
│   ├── core/               # App configuration, security, dependencies
│   ├── auth/               # Authentication features
│   ├── users/              # User management features
│   ├── boards/             # Board management features
│   ├── pins/               # Pin management features
│   ├── tags/               # Tagging features
│   ├── database.py         # Database configuration
│   └── main.py             # Application entry point
└── tests/                  # Pytest test suite
```

## 🧪 Testing

The project uses `pytest`. Make sure your `.env.test` is configured or mock values are supplied.
To run tests locally:
```bash
pytest
```
To run tests inside Docker:
```bash
docker compose exec api pytest
```
