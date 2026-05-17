# CareerOS

A local-first career intelligence system that scrapes job boards, maps your resume against the market using vector embeddings, and generates a prioritized weekly action plan.

**Status:** MVP — database layer complete, agents in progress.

---

## What it does

1. **Scrapes** job postings from Greenhouse, Lever, and Ashby APIs
2. **Embeds** every job using OpenAI `text-embedding-3-small` and stores vectors in PostgreSQL via pgvector
3. **Clusters** jobs into role archetypes using KMeans (e.g. "ML Platform Engineering", "Analytics Engineering")
4. **Maps** your resume against each cluster using cosine similarity
5. **Generates** a ranked list of career directions with skill gaps, skill matches, and LLM reasoning
6. **Produces** a weekly execution plan with specific job targets and tailored resume variants

---

## Architecture

```
Layer 1 — Data        Scrapers → Normalizer → PostgreSQL
Layer 2 — Intelligence  Embeddings → Clustering → Career Mapping
Layer 3 — Decision    Strategy Agent → Execution Plan
Layer 4 — Interface   CLI (primary) · FastAPI (secondary)
```

Full design: [`docs/system_design.md`](docs/system_design.md)

---

## Tech stack

| Component | Technology |
|---|---|
| Database | PostgreSQL 17 + pgvector |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) |
| LLM | OpenAI GPT-4o-mini |
| Clustering | scikit-learn KMeans |
| HTTP | httpx (async) |
| CLI | Typer + Rich |
| Config | pydantic-settings |

---

## Prerequisites

- Python 3.11+
- PostgreSQL 17 with pgvector extension (local install or Docker)
- OpenAI API key

---

## Setup

**1. Clone and create environment**
```bash
git clone https://github.com/your-username/CareerOS.git
cd CareerOS

uv venv
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\Activate.ps1      # Windows PowerShell

uv pip install -e .
```

**2. Configure environment**
```bash
cp .env.example .env
# Edit .env and fill in your values
```

**3. Start the database**

Option A — Docker (recommended for contributors):
```bash
docker-compose up -d
```

Option B — Local Postgres (if already installed):
```bash
# Create the database
psql -U postgres -c "CREATE DATABASE careeros;"
```

**4. Apply the schema**

Mac/Linux:
```bash
psql postgresql://postgres:PASSWORD@localhost:5432/careeros -f database/migration/schema.sql
```

Windows PowerShell:
```powershell
Get-Content database/migration/schema.sql | docker exec -i careeros_db psql -U postgres -d careeros
# or if using local Postgres:
Get-Content database/migration/schema.sql | psql -U postgres -d careeros
```

**5. Verify the connection**
```bash
python scripts/seed_db.py
```

Expected output:
```
✓ Inserted job <uuid>
✓ Found 1 job(s)
  • Data Engineer @ Acme Corp
```

---

## Environment variables

Copy `.env.example` to `.env` and fill in:

```
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/careeros
OPENAI_API_KEY=sk-...
```

Never commit `.env` — it is in `.gitignore`. Only `.env.example` is committed.

---

## Project structure

```
CareerOS/
├── core/                  # All intelligence and business logic
│   ├── collectors/        # ATS scrapers (Greenhouse, Lever, Ashby)
│   ├── normalization/     # Job normalizer
│   ├── embeddings/        # Job + resume embedders
│   ├── clustering/        # KMeans clustering
│   ├── ranking/           # Career mapping (Agent 2)
│   ├── strategy/          # Execution engine (Agent 3)
│   └── workflows/         # Full pipeline orchestration
├── database/              # Persistence layer only
│   ├── models/            # SQLAlchemy ORM models
│   ├── migration/         # schema.sql + Alembic migrations
│   ├── base.py            # Declarative base
│   └── session.py         # Async session factory
├── cli/                   # Primary interface
├── api/                   # FastAPI wrapper (secondary)
├── mcp_server/            # Future MCP tool integration
├── exports/               # All output files (JSON, Excel, resumes)
├── docs/                  # System design and agent documentation
├── scripts/               # seed_db.py and local run helpers
└── tests/                 # Test suite
```

---

## Database

10 tables across 3 layers. Full reference: [`docs/database.md`](docs/database.md)

```
Layer 1  jobs · job_embeddings · clustering_runs · role_clusters · job_cluster_memberships
Layer 2  resumes · resume_embeddings · rankings
Layer 3  execution_plans · execution_actions
```

---

## Roadmap

- [x] PostgreSQL schema with pgvector
- [x] Async SQLAlchemy models
- [x] Database connection verified
- [ ] Agent 1 — Market Intelligence (scrapers + embeddings + clustering)
- [ ] Agent 2 — Career Mapping (resume embedding + ranking)
- [ ] Agent 3 — Strategy & Execution (plan generation)
- [ ] CLI commands (ingest, analyze, export, pipeline)
- [ ] FastAPI wrapper
- [ ] MCP server tools

---

## Contributing

This is a single-user local tool in active development. Structure and interfaces may change between phases.