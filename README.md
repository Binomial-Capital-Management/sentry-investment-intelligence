# Sentry Investment Intelligence

An AI-driven investment research and risk analytics platform. Users ask questions in natural language; a LangGraph supervisor routes them to specialist agents that pull market data, run quantitative models, and return tables, charts, and reports.

> **Status:** This project is no longer actively developed or maintained. The code is published as-is for reference and reuse. Issues and pull requests may not receive a response.

## Features

- **Multi-agent chat**: a LangGraph supervisor routes each request to specialist agents (risk, comparable companies, DCF, options, quant coding, charting, document analysis, screening, institutional activity, prediction markets, and more).
- **Risk and portfolio analytics**: Value at Risk / CVaR, Monte Carlo simulation, efficient-frontier optimization, Barra-style factor decomposition, hedge construction, option pricing and Greeks.
- **Market data via MCP servers**: Financial Modeling Prep, Yahoo Finance, Polygon, FRED, SEC EDGAR, Unusual Whales, Quiver Quant, and Polymarket, with dynamic field discovery instead of hardcoded schemas.
- **Canvas workspace**: datasets, pivot tables, charts, and tool workflows in a single workspace.
- **Excel add-in**: an Office add-in that brings the agent into a spreadsheet.
- **Multi-tenant by design**: PostgreSQL row-level security (RLS) isolates every user's data; authentication through Clerk.
- **BinomialHash**: a standalone Python package that compacts large structured tool outputs for LLM context windows (see [`binomialhash/`](binomialhash/)).

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+, FastAPI, LangGraph, OpenAI Agents SDK |
| Frontend | React 18, TypeScript, Vite |
| Data | PostgreSQL (with RLS), Redis (optional cache), SQLite (agent state) |
| Auth | Clerk (JWT) |
| Infra | Docker, AWS ECS / S3 / CloudFront, Terraform, GitHub Actions |

## Repository layout

```
app_fastapi.py          FastAPI entry point
api/                    REST routers, middleware, request/response models
core/
  agents/               Specialist agents, tools, and prompts
  ai/                   LangGraph orchestrator and nodes
  mcp_servers/          Market-data servers (FMP, Polygon, SEC, FRED, ...)
  risk_modules/         VaR, Monte Carlo, optimization, factor models
  database/             PostgreSQL client with RLS helpers
frontend/               React + Vite web app
sentry-excel-addin/     Microsoft Excel add-in
binomialhash/           Standalone payload-compaction package
alembic/                Database migrations
infrastructure/         Terraform for AWS
lambdas/                Scheduled AWS Lambda jobs
tests/                  Backend test suite
benchmarks/             BinomialHash benchmarks
```

## Getting started

### Prerequisites

- Python 3.9 or newer
- Node.js 18 or newer
- PostgreSQL 14 or newer (optional for chat-only use; required for portfolios, sessions, and user data)
- API keys for the services you want to use. An OpenAI key is required; market-data keys such as FMP are needed for most analytics.

### 1. Configure the environment

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Fill in at least `OPENAI_API_KEY`. To enable the database, set `DATABASE_URL` and `ENABLE_POSTGRES=true`. Every other key is optional and enables the matching integration. `.env.example` documents each variable.

For local development without Clerk, set `DEV_SECRET` in `.env` and `VITE_DEV_SECRET` in `frontend/.env` to the same random value. The development auth path is disabled when `ENVIRONMENT=production`.

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate
make install          # Python + frontend dependencies
```

### 3. Run database migrations (if using PostgreSQL)

```bash
alembic upgrade head
```

### 4. Start the app

```bash
make dev-py           # backend on http://localhost:8002 (API docs at /docs)
make dev-ts           # frontend on http://localhost:3000
```

To run the Excel add-in, see `sentry-excel-addin/package.json` (`npm run dev`, then `npm start` to sideload).

### Docker

```bash
docker build -t sentry-backend .
docker run --env-file .env -p 8002:8002 sentry-backend
```

## Development

```bash
make test             # backend and frontend tests
make lint             # linters
make type-check       # mypy and tsc
make help             # all available targets
```

Some tests call external APIs and need the matching keys set in `.env`.

## Using BinomialHash on its own

```bash
pip install -e ./binomialhash
```

See [`binomialhash/examples/`](binomialhash/examples/) for usage examples.

## License

Released under the MIT License, as declared in `pyproject.toml`. Copyright © Binomial Capital Management.

Third-party logos, icons, and brand names in this repository belong to their respective owners and are included only to identify the corresponding integrations.
