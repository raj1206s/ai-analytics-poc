# Loan Analytics Agent POC

Dockerized self-service analytics chat for education loan origin data. Uses **PostgreSQL**, **governed DAX-aligned metrics**, **Google Gemini**, and **LangGraph** — following Anthropic's agentic analytics pattern (metrics first, curated docs, read-only SQL fallback).

## Architecture

- **postgres** — `application`, `disbursement`, `credit_history`, `dim_date`, `semantic.*`
- **api** — FastAPI + LangGraph agent (`plan → agent ⇄ tools → verify → answer`) on Gemini
- **web** — Next.js chat UI with provenance panel

### LangGraph flow

1. **plan** — short execution plan (date window, preferred metrics)
2. **agent** — Gemini with bound analytics tools
3. **tools** — governed metrics / docs / read-only SQL
4. **verify** — checks tools-used-for-KPIs + provenance footer; may retry
5. **answer** — final streamed response

## Quick start

1. Copy environment file and add your Gemini key:

```bash
cp .env.example .env
# Edit .env: GEMINI_API_KEY=your_key_here
```

2. Start all services:

```bash
docker compose up --build
```

3. Open the chat UI: [http://localhost:3000](http://localhost:3000)

4. API health: [http://localhost:8000/health](http://localhost:8000/health)

## Governed metrics (Power BI DAX → SQL)

| Metric | Time axis |
|--------|-----------|
| Logins (LD) | login_date |
| Loan Amount (LD) | login_date |
| Sanctions (All) | sanction_date |
| Sanction Amount (All) | sanction_date |
| First Disbursed (All) | disbursement_date (tranche=1) |
| First Disbursed Amount (All) | disbursement_date (tranche=1) |

## Application statuses (seed data)

`logged`, `under_cm_review`, `credit_declined`, `customer_declined`, `sanctioned`, `disbursement_review`, `first_disbursed`

## Example questions

- What were Logins (LD) in March 2025?
- Show Sanction Amount (All) by branch for Q2 2025
- How many applications are credit declined in Q1 2025?
- Loans under CM review with more info required

## Run offline evals

With Postgres running locally:

```bash
cd api
pip install -r requirements.txt
DATABASE_URL=postgresql://analytics:analytics@localhost:5432/loan_analytics python evals/run_evals.py
```

## Project layout

```
db/init/          PostgreSQL schema, semantic layer, seed data
api/app/          FastAPI + LangGraph/Gemini agent + skills
api/app/agent/    graph.py (LangGraph), langchain_tools.py, tools.py
api/evals/        Seed-pinned eval questions
web/              Next.js chat UI
```

## Configuration

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key (required for chat) |
| `GEMINI_MODEL` | Default: `gemini-2.0-flash` |
| `DATABASE_URL` | Postgres connection string |

## Notes

- Timezone default for relative dates: **Asia/Kolkata** (calendar months)
- Agent uses LangGraph (`plan → agent ⇄ tools → verify → answer`); metrics before raw SQL
- PII columns are excluded from agent guidance
