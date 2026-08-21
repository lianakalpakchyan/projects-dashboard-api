# Projects Dashboard API

A REST API for managing projects and their documents, built with FastAPI. Users can sign up, create projects, invite others by email, and upload/download documents (PDFs, Word files, images) that are stored in S3. Uploaded images are automatically resized by a Lambda function, and each project's storage usage is tracked against a configurable limit.

## Features

- **Auth** — user registration and login with JWT access tokens
- **Projects** — create, update, list, and delete projects
- **Sharing** — invite a user by email or generate a join link/token to share a project
- **Documents** — upload, download, replace, and delete files attached to a project
- **Storage limits** — per-project storage cap enforced on upload
- **Image resizing** — uploaded images are resized via an AWS Lambda handler
- **Structured logging** — request latency and status logged for every call

## Tech stack

- **FastAPI** + **Uvicorn** — web framework and server
- **SQLAlchemy** + **Alembic** — ORM and database migrations
- **PostgreSQL** — primary database
- **AWS S3 / Lambda** (via **boto3**) — document storage and image processing
- **JWT** (python-jose) + **Passlib (bcrypt)** — authentication
- **pytest**, **ruff**, **mypy** — testing and code quality

## Getting started

### Prerequisites

- Python 3.13+
- [Poetry](https://python-poetry.org/)
- Docker and Docker Compose (recommended, includes PostgreSQL)

### 1. Configure environment variables

Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

Key variables you'll want to check:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Secret used to sign JWTs (min. 32 characters) |
| `POSTGRES_*` | Database connection settings |
| `AWS_*`, `S3_BUCKET_NAME`, `S3_ENDPOINT_URL` | S3 credentials/bucket for document storage |
| `MAX_PROJECT_STORAGE_MB` | Storage quota per project |
| `MAX_IMAGE_DIMENSION` | Max width/height for resized images |

### 2. Run with Docker Compose (recommended)

```bash
docker compose up --build
```

This starts PostgreSQL, runs database migrations, and launches the API with hot-reload at `http://localhost:8000`.

### 3. Run locally without Docker

```bash
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

Make sure a PostgreSQL instance matching your `.env` settings is running first.

## API documentation

Once the server is running, interactive API docs are available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Main endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth` | Register a new user |
| `POST` | `/login` | Log in and receive a JWT |
| `POST` | `/projects` | Create a project |
| `GET` | `/projects` | List your projects |
| `GET` | `/projects/{id}/info` | Get project details |
| `PUT` | `/projects/{id}/info` | Update a project |
| `DELETE` | `/projects/{id}` | Delete a project |
| `POST` | `/projects/{id}/invite` | Invite a user by email |
| `GET` | `/projects/{id}/share` | Generate a shareable join link |
| `POST` | `/projects/join` | Join a project via token |
| `GET` | `/projects/{id}/documents` | List documents in a project |
| `POST` | `/projects/{id}/documents` | Upload one or more documents |
| `GET` | `/documents/{id}` | Download a document |
| `PUT` | `/documents/{id}` | Replace a document |
| `DELETE` | `/documents/{id}` | Delete a document |
| `GET` | `/health` | Health check |

All endpoints except `/auth`, `/login`, and `/health` require a bearer token from `/login`.

## Running tests

```bash
poetry run pytest
```

This runs both the API tests (`tests/`) and the Lambda tests (`lambdas/tests/`), with coverage reporting.

## Project structure

```
app/
├── api/          # Routers and dependency wiring
├── core/         # Config, security, logging, S3, AWS deployment helpers
├── db/           # Database session/base setup
├── models/       # SQLAlchemy models
├── repositories/ # Data access layer
├── schemas/      # Pydantic request/response models
├── services/     # Business logic
└── main.py       # FastAPI app entrypoint

lambdas/          # AWS Lambda handlers (image resize, storage size calculation)
alembic/          # Database migrations
tests/            # API test suite
```