# AI Business Management Platform

Modular monolith: FastAPI + PostgreSQL/pgvector + Redis, with an AI orchestration layer planned
(extraction, RAG, agent, MCP). React frontend arrives in Phase 2.

**Status: Phase 1 (foundation) complete.** Working: authentication (JWT, logout/revocation), RBAC,
user and role administration, structured logging, uniform error responses, Docker Compose, CI.
Next: Phase 2 (customers, products, inventory, orders). Design: [docs/01-phase1-architecture.md](docs/01-phase1-architecture.md).

## Run everything in Docker (recommended)

Prerequisites: Docker Desktop.

```powershell
# 1. config: edit .env (set POSTGRES_PASSWORD, make DATABASE_URL match, set SECRET_KEY >= 32 chars)
Copy-Item .env.example .env

# 2. start PostgreSQL + Redis + backend (migrations and RBAC seed run automatically on start)
docker compose --env-file .env -f infrastructure/docker-compose.yml up -d --build

# 3. create the first administrator (prompts for a password)
docker compose --env-file .env -f infrastructure/docker-compose.yml exec backend `
  python -m app.modules.users.create_admin --email you@example.com --full-name "Your Name"
```

Backend: http://127.0.0.1:8000 (Swagger UI at `/docs` unless `APP_ENV=production`).
Logs: `docker compose --env-file .env -f infrastructure/docker-compose.yml logs -f backend`.

## Develop locally (backend on the host, DB/Redis in Docker)

Prerequisites: Python 3.12, Docker Desktop, Git.

```powershell
docker compose --env-file .env -f infrastructure/docker-compose.yml up -d db redis   # 127.0.0.1:5433 / :6379

cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.modules.auth.seed          # roles + permissions (idempotent)
.\.venv\Scripts\python.exe -m app.modules.users.create_admin --email you@example.com --full-name "Your Name"
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
```

`create_admin` prompts for the password (or reads `ADMIN_PASSWORD`); if the user already exists it
promotes them to admin and leaves their password unchanged.

## API overview (Phase 1)

| Method & path | Needs | Purpose |
|---|---|---|
| `GET /health`, `GET /health/ready` | - | liveness; readiness (database + Redis) |
| `POST /api/v1/auth/register` | - | self-register; always gets the `employee` role |
| `POST /api/v1/auth/login` | - | returns a Bearer token (default 30 min) |
| `POST /api/v1/auth/logout` | token | revokes that token (Redis denylist) |
| `GET /api/v1/users/me` | token | own profile, roles, permissions |
| `GET /api/v1/users`, `GET /api/v1/users/{id}` | `user:read` | list (paginated) / read users |
| `PUT /api/v1/users/{id}/roles` | `user:manage` | replace a user's roles |
| `PATCH /api/v1/users/{id}` | `user:manage` | enable / disable a user |
| `GET /api/v1/roles` | `user:read` | roles with their permissions |
| `PUT /api/v1/roles/{id}/permissions` | `role:manage` | replace a role's permissions (not `admin`) |

Errors always look like `{"error": {"code", "message", "request_id", "details"}}`; the same id is
returned in the `X-Request-ID` header and appears in every log line of that request.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -m "not integration"   # unit, no services needed
.\.venv\Scripts\python.exe -m pytest                        # everything; needs db + redis running
```

Integration tests create a throw-away `<db>_test` database and run the real Alembic migrations in
it, and use Redis logical DB 15, so your development data is never touched. CI
(`.github/workflows/ci.yml`) runs the same suite against PostgreSQL+pgvector and Redis service containers.

## Troubleshooting

- Use `127.0.0.1` rather than `localhost` in URLs on Windows: `localhost` may resolve to IPv6 first,
  which Docker does not publish, causing slow connections.
- Host port 5433 (not 5432) is used for the container's PostgreSQL so it does not clash with a
  locally installed PostgreSQL. Change `POSTGRES_PORT` and `DATABASE_URL` together if needed.
- The app refuses to start if `DATABASE_URL`, `REDIS_URL` or `SECRET_KEY` (>= 32 chars) is missing.
- Registration returns 500 "run the RBAC seed" if roles were never seeded (the Docker setup seeds on start).

## Known limitations (planned for later phases)

- No rate limiting / lockout on login attempts yet (Phase 6, AI guardrails and rate limiting).
- No refresh tokens; access tokens last `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Registering an already used email returns 409, which reveals that the email exists.
- Migrations run on container start: fine for one instance; run them as a separate job when scaling out.
