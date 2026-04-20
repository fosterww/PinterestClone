# Pinterest Clone Monorepo

Pinterest-style application split into:

- `backend-pinterest`: FastAPI API, async PostgreSQL access, Redis rate limiting/cache, RabbitMQ + Celery workers, MinIO media storage, and AI-assisted discovery/moderation services.
- `frontend-pinterest`: React + TypeScript + Vite client for authentication, feed browsing, pin creation, filtering, and pin detail views.

## Current Architecture

### Frontend

- React 19 + TypeScript + Vite
- TanStack Query for server state
- Axios client pointed at `/api/v2`
- Local token storage with logout on `401`
- Google OAuth client support

The frontend runs on `http://localhost:5173` in development and proxies `/api` requests to the backend at `http://localhost:8000`.

### Backend

- FastAPI app with routers mounted under `/api/v2`
- Async SQLAlchemy + `asyncpg` for PostgreSQL access
- Alembic migrations
- Redis-backed rate limiting via `slowapi`
- JWT auth with refresh tokens and server-side session handling
- RabbitMQ + Celery for background jobs
- MinIO for image storage
- AI integrations:
  - Gemini for automatic image tag generation
  - Toxic-BERT for comment moderation
  - Clarifai for image indexing and related-pin search

### Feature Modules

Backend code is organized by domain:

- `auth`: register, login, Google login, refresh, logout
- `users`: current user, public profiles, followers/following, follow/unfollow
- `boards`: CRUD-style board flows and pin-to-board management
- `pins`: create/list/detail/update/delete, likes, comments, related pins
- `pins.service.discovery`: personalized feed and tag-visit tracking
- `core`: config, dependencies, security, infra clients, exceptions, logging

### Request / Data Flow

1. The React app calls `/api/v2/...` through the Vite proxy.
2. FastAPI routers delegate work to service and repository layers.
3. PostgreSQL stores users, boards, pins, comments, tags, follows, and sessions.
4. Images are stored in MinIO and can be indexed in Clarifai.
5. Redis is used for rate limiting and app-level caching concerns.
6. Celery workers handle asynchronous tasks such as Clarifai image indexing and deletion.
7. Discovery features combine follow relationships, recent activity, visited tags, and related-image search.

## Repository Layout

```text
.
|-- backend-pinterest/
|   |-- src/
|   |   |-- auth/
|   |   |-- boards/
|   |   |-- core/
|   |   |-- pins/
|   |   |-- tags/
|   |   |-- users/
|   |   |-- database.py
|   |   `-- main.py
|   |-- migrations/
|   |-- tests/
|   |-- docker-compose.yaml
|   `-- pyproject.toml
|-- frontend-pinterest/
|   |-- src/
|   |   |-- api/
|   |   |-- components/
|   |   |-- context/
|   |   `-- types/
|   |-- public/
|   |-- package.json
|   `-- vite.config.ts
`-- README.md
```

## Prerequisites

Required:

- Python 3.12+
- Node.js 20+
- Docker Desktop / Docker Engine with Compose

For local development without Dockerized app processes, you still need the infrastructure services:

- PostgreSQL
- Redis
- RabbitMQ
- MinIO

Optional third-party credentials unlock the AI-assisted features:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GEMINI_API_KEY`
- `CLARIFAI_API_KEY`
- `CLARIFAI_USER_ID`
- `CLARIFAI_APP_ID`

## Backend Setup

From `backend-pinterest/`:

### 1. Create environment variables

This project loads backend settings from `.env`.

Typical values:

```env
DB_USER=postgres
DB_PASSWORD=secret
DB_NAME=pinterest
DB_HOST=localhost
DB_PORT=5432

JWT_SECRET_KEY=change-me-in-production

S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=pinterest
S3_PUBLIC_BASE_URL=http://localhost:9000/pinterest

REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://pinterest:pinterest@localhost:5672//

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GEMINI_API_KEY=
CLARIFAI_API_KEY=
CLARIFAI_USER_ID=
CLARIFAI_APP_ID=
```

### 2. Start infrastructure

```bash
docker compose up -d db redis rabbitmq minio minio-init
```

### 3. Install Python dependencies

```bash
uv sync
```

### 4. Run migrations

```bash
uv run alembic upgrade head
```

### 5. Start the API

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Backend With Docker

If you want the backend services and workers containerized, from `backend-pinterest/`:

```bash
docker compose up --build -d
```

This compose file starts:

- `db`
- `minio`
- `minio-init`
- `redis`
- `rabbitmq`
- `celery`
- `celery-beat`
- `api`
- `nginx`

After startup:

```bash
docker compose exec api alembic upgrade head
```

## Frontend Setup

From `frontend-pinterest/`:

### 1. Install dependencies

```bash
npm install
```

### 2. Start the development server

```bash
npm run dev
```

The Vite app runs on `http://localhost:5173` and proxies `/api` traffic to `http://localhost:8000`.

If you use Google login in the UI, configure the frontend environment accordingly.

## Main API Areas

Current mounted routers:

- `/api/v2/auth`
- `/api/v2/users`
- `/api/v2/pins`
- `/api/v2/boards`

Notable implemented flows:

- Email/password registration and login
- Google token login
- Access-token refresh and logout
- Create, browse, update, like, and delete pins
- Pin comments with like/unlike flows
- Related pin search
- Personalized feed
- User profiles, follow/unfollow, followers/following
- User boards and board membership management

## Testing

### Backend tests

From `backend-pinterest/`:

```bash
uv run pytest
```

The test suite includes API, service, and core/infrastructure coverage for auth, users, boards, pins, security, S3, Clarifai, and personalized feed behavior.