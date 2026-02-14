# Apeiron Data Sentinel

**Multi-Client Data Validation & Governance Engine**

Replaces Excel-based reconciliation (VLOOKUP, manual joins, formulas) for freight audit operations. Supports 50+ clients, 180 concurrent users, and is fully Dockerized for seamless deployment.

---

## Architecture

| Layer | Technology | Purpose |
|---|---|---|
| API | FastAPI (async) | REST endpoints |
| Engine | Polars | Data validation & analytics |
| Database | PostgreSQL 16 | Persistent storage |
| Pooling | PgBouncer | Connection pooling (180 users) |
| Cache/Queue | Redis 7 | Background tasks |
| AI Assistant | Ollama (Mistral) | Local-only AI explanations |
| Proxy | Nginx | Reverse proxy, rate limiting, HTTPS |

All services run via **Docker Compose**.

---

## Quick Start (Development)

### Prerequisites

- Docker & Docker Compose
- Git

### 1. Clone & Configure

```bash
git clone https://github.com/anandrobert-dev/apeiron_data_sentinel.git
cd apeiron_data_sentinel
cp .env.example .env
# Edit .env — change JWT_SECRET_KEY and POSTGRES_PASSWORD
```

### 2. Start Services

```bash
docker compose up --build -d
```

### 3. Run Database Migrations

```bash
docker compose exec app alembic upgrade head
```

### 4. Create SuperAdmin User

```bash
docker compose exec app python -c "
from app.core.security import hash_password
print('Use this hash in a DB insert:', hash_password('YourSecurePassword'))
"
```

Or use the API after the first SuperAdmin is created.

### 5. Access the System

- **API Docs**: <http://localhost/docs>
- **Health Check**: <http://localhost/api/health>
- **Ollama AI**: <http://localhost:11434>

---

## Project Structure

```
apeiron_data_sentinel/
├── app/
│   ├── main.py              # FastAPI entrypoint
│   ├── config.py            # Environment settings
│   ├── database.py          # Async SQLAlchemy
│   ├── models/              # ORM models (User, Client, Rule, etc.)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── api/                 # Route handlers
│   │   ├── auth.py          # Login, register
│   │   ├── users.py         # User CRUD
│   │   ├── clients.py       # Client CRUD
│   │   ├── rules.py         # Rule CRUD + approval
│   │   ├── validation.py    # File upload & validation
│   │   ├── grace.py         # AI assistant
│   │   └── health.py        # Health checks
│   ├── core/
│   │   ├── security.py      # JWT, bcrypt
│   │   └── rbac.py          # Role-based access control
│   ├── engine/
│   │   ├── loader.py        # CSV/Excel → Polars
│   │   ├── validator.py     # Rule engine orchestrator
│   │   ├── duplicates.py    # Duplicate detection
│   │   ├── mismatches.py    # Cross-file mismatches
│   │   ├── reconciliation.py # GL validation, summaries
│   │   └── reporter.py      # Excel report generation
│   └── services/
│       └── grace_service.py # Ollama AI client
├── alembic/                 # Database migrations
├── nginx/                   # Reverse proxy config
├── docker-compose.yml       # Development
├── docker-compose.prod.yml  # Production overrides
├── Dockerfile
├── .env.example
└── requirements.txt
```

---

## RBAC Roles

| Role | Permissions |
|---|---|
| **SuperAdmin** | Full access, create users, approve rules |
| **RuleApprover** | Approve/reject rules, view all clients |
| **AccountManager** | Create rules (needs approval), manage assigned clients |
| **ValidatorUser** | Upload files, run validations |
| **Auditor** | Read-only access, view logs |

---

## Rule Governance

1. **AccountManager** creates a rule → `enabled=False`
2. **RuleApprover** reviews and approves → `enabled=True`
3. Every change bumps `version` and creates a `RuleHistory` snapshot
4. Rules have `effective_from` / `effective_to` date ranges
5. Global rules (`client_id=NULL`) apply to all clients

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Login, get JWT |
| POST | `/api/auth/register` | Register user (SuperAdmin) |
| GET | `/api/users/me` | Current user profile |
| GET/POST | `/api/clients/` | List/create clients |
| GET/POST | `/api/rules/` | List/create rules |
| POST | `/api/rules/{id}/approve` | Approve/reject rule |
| POST | `/api/validation/run/{client_id}` | Upload & validate |
| GET | `/api/validation/history/{client_id}` | Validation history |
| POST | `/api/grace/explain` | AI failure explanation |
| POST | `/api/grace/suggest-rule` | AI rule suggestion |
| GET | `/api/health` | System health check |

---

## Desktop → VPS Migration

### 1. Prepare Production Environment

```bash
# On VPS
sudo apt update && sudo apt install docker.io docker-compose-v2
git clone https://github.com/anandrobert-dev/apeiron_data_sentinel.git
cd apeiron_data_sentinel
```

### 2. Configure Production Settings

```bash
cp .env.example .env
# Set ENVIRONMENT=production
# Set strong JWT_SECRET_KEY and POSTGRES_PASSWORD
# Set ALLOWED_ORIGINS to your domain
```

### 3. Set Up HTTPS (Let's Encrypt)

```bash
# Install certbot and generate certs
sudo certbot certonly --standalone -d yourdomain.com
mkdir -p nginx/certs
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/certs/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/certs/
```

### 4. Deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose exec app alembic upgrade head
```

### 5. Migrate Data (if needed)

```bash
# Export from desktop
docker compose exec postgres pg_dump -U sentinel apeiron_sentinel > backup.sql

# Import on VPS
docker compose exec -T postgres psql -U sentinel apeiron_sentinel < backup.sql
```

---

## Security

- **JWT authentication** with configurable expiry
- **bcrypt password hashing**
- **RBAC enforcement** on all endpoints
- **Nginx rate limiting** (30 req/s API, 5 req/s auth)
- **File type & size validation**
- **Audit logging** for all rule changes and validation runs
- **No external API calls** — all AI processing is local
- **SQL injection prevention** via SQLAlchemy parameterized queries

---

## Environment Variables

See [.env.example](.env.example) for all configurable settings.

Key variables:

- `JWT_SECRET_KEY` — **Must be changed** for production
- `POSTGRES_PASSWORD` — **Must be changed** for production
- `ENVIRONMENT` — `development` or `production`
- `PG_SHARED_BUFFERS` / `PG_WORK_MEM` — PostgreSQL tuning for 32GB RAM
