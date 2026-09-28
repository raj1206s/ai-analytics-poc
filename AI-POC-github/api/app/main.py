from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent.agent import AnalyticsAgent
from app.config import settings
from app.db import run_query

app = FastAPI(title="Loan Analytics Agent API", version="1.0.0")

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = AnalyticsAgent()


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] | None = None


class MetricRunRequest(BaseModel):
    name: str
    start_date: str
    end_date: str
    group_by: str | None = None


@app.get("/health")
def health():
    try:
        run_query("SELECT 1 AS ok")
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "gemini_configured": bool(settings.gemini_api_key),
    }


@app.get("/api/metrics")
def api_list_metrics(q: str | None = None):
    from app.agent import tools

    return tools.list_metrics(q)


@app.post("/api/metrics/run")
def api_run_metric(body: MetricRunRequest):
    from app.agent import tools

    try:
        return tools.run_metric(body.name, body.start_date, body.end_date, body.group_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat")
async def chat(body: ChatRequest):
    async def event_generator():
        import json

        try:
            async for event in agent.chat(body.message, body.history):
                yield {"event": event["type"], "data": json.dumps(event, default=str)}
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "content": str(exc)}),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/suggested-prompts")
def suggested_prompts():
    return [
        "What were Logins (LD) in March 2025?",
        "Show Sanction Amount (All) by branch for Q2 2025",
        "How many Sanctions (All) in Q1 2025?",
        "What was Loan Amount (LD) in March 2025?",
        "How many First Disbursed (All) in July 2025?",
        "First Disbursed Amount (All) YTD through August 2025",
        "Loan Amount (LD) MTD for August 2025",
        "Show Logins (LD) by branch for March 2025",
        "Sanction Amount (All) by product for Q1 2025",
        "How many applications are credit declined in Q1 2025?",
        "How many applications are under CM review?",
        "Applications under CM review with more info required",
    ]
