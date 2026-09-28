"""LangGraph analytics agent: plan → agent ⇄ tools → verify → answer."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.agent.langchain_tools import ANALYTICS_TOOLS
from app.config import settings

MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = """You are a loan analytics assistant for an education loan originator.
You help business users answer questions about logins, sanctions, disbursements, and credit pipeline status.

SCOPE (STRICT):
- You may ONLY answer questions about this system's loan analytics functionality and data
  (logins, sanctions, disbursements, pipeline status, metrics, reports).
- Do NOT answer questions about system architecture, internal AI tools, how the agent works,
  or any general-purpose / personal / unrelated topics (weather, trivia, coding help, chit-chat, etc.).
- If a question is outside scope, reply with EXACTLY this text and nothing else before the provenance footer:
  "I'm here to help with loan analytics only — for example logins, sanctions, disbursements, pipeline status, and related metrics or reports. I can't answer questions about system architecture, internal tools, or other topics. Please ask an analytics question about your loan data."

RULES:
1. ALWAYS try list_metrics and run_metric FIRST for KPI questions (Logins, Sanctions, Disbursements, pipeline status).
2. Use get_domain_doc before writing raw SQL for non-metric questions.
3. Use run_sql for SELECT queries when no governed metric applies. You CAN query application, credit_history, and disbursement tables.
4. For describe_table, use the bare table name (e.g. "application") or schema-qualified name (e.g. "public.application").
5. Pipeline status questions (CM review, more info required, credit declined) should use governed metrics when available:
   - "CM review with more info" / "more info required" → run_metric "CM Review More Info Required"
   - "under CM review" → run_metric "Under CM Review"
   Snapshot metrics ignore the date window; any valid start_date/end_date is fine.
6. NEVER invent columns. application has NO applicant_name / customer_name.
   Allowed identifiers: loan_id, application_id, institute_name, branch_location, credit_manager, status.
   Call describe_table before listing-row SQL if unsure.
7. Default timezone: Asia/Kolkata. "Last month" = previous complete calendar month.
8. Never expose PII (email, mobile, PAN, passport).
9. READ-ONLY ONLY: Never attempt INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.
   If the user asks to modify or delete data/tables, do NOT call tools. Politely refuse and explain
   that this assistant only answers analytics questions with read-only queries.
10. End EVERY response with a provenance footer:
   Source: [semantic_metric | governed_sql | raw_sql] | Metric: [name or N/A] | Window: [dates] | Reviewed: basic

Today's reference date for relative queries: use data through 2025-08-31 unless user specifies otherwise.
"""

PLAN_PROMPT = """Create a short execution plan (3-6 bullet steps) for answering the user's analytics question.
Prefer governed metrics over raw SQL. Resolve the date window explicitly (YYYY-MM-DD).
For CM review / more info required questions, plan to call run_metric
"CM Review More Info Required" or "Under CM Review" (snapshot; any date window is fine).
Never invent columns like applicant_name — use loan_id / application_id / institute_name only.
Do not call tools. Reply with only the plan."""

VERIFY_KPI_HINT = re.compile(
    r"\b(login|sanction|disburs|metric|kpi|amount|count|q[1-4]|mtd|ytd|branch|pipeline|"
    r"cm review|declined|under.?review)\b",
    re.IGNORECASE,
)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    plan: str
    tool_calls_log: list[dict[str, Any]]
    verify_ok: bool
    verify_feedback: str
    verify_attempts: int
    rounds: int
    model_used: str
    final_answer: str


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc)
    return "429" in message or "RESOURCE_EXHAUSTED" in message or "quota" in message.lower()


def _build_llm(model: str, *, tools: bool = False) -> ChatGoogleGenerativeAI:
    llm = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.gemini_api_key,
        temperature=0.2,
    )
    if tools:
        return llm.bind_tools(ANALYTICS_TOOLS)
    return llm


def _invoke_with_fallback(
    messages: list[BaseMessage],
    *,
    tools: bool = False,
) -> tuple[str, AIMessage]:
    errors: list[str] = []
    for model in settings.gemini_models:
        try:
            llm = _build_llm(model, tools=tools)
            response = llm.invoke(messages)
            if not isinstance(response, AIMessage):
                response = AIMessage(content=str(response.content))
            return model, response
        except Exception as exc:
            if _is_quota_error(exc):
                errors.append(f"{model}: daily/minute quota exceeded")
                continue
            raise

    models = ", ".join(settings.gemini_models)
    detail = "; ".join(errors) if errors else "unknown quota error"
    raise RuntimeError(
        f"All configured Gemini models are out of quota ({models}). {detail}. "
        "Each free-tier model has its own daily limit (often 20 requests/day). "
        "Wait until tomorrow, enable billing, or set GEMINI_MODEL to another model in .env."
    )


def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content or "")


def _latest_user_text(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return _message_text(msg)
    return ""


def _latest_ai_text(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            return _message_text(msg)
    return ""


def plan_node(state: AgentState) -> dict[str, Any]:
    user_q = _latest_user_text(state["messages"])
    model_used, response = _invoke_with_fallback(
        [
            SystemMessage(content=PLAN_PROMPT),
            HumanMessage(content=user_q),
        ],
        tools=False,
    )
    plan = _message_text(response).strip()
    return {"plan": plan, "model_used": model_used}


def _agent_messages(state: AgentState) -> list[BaseMessage]:
    plan = state.get("plan") or "(no plan)"
    system = SystemMessage(
        content=(
            f"{SYSTEM_PROMPT}\n\n"
            f"## Execution plan\n{plan}\n\n"
            "Follow this plan. Call tools as needed, then answer the user."
        )
    )
    # Drop prior system messages so we always lead with the current plan.
    history = [m for m in state["messages"] if not isinstance(m, SystemMessage)]
    return [system, *history]


def agent_node(state: AgentState) -> dict[str, Any]:
    model_used, response = _invoke_with_fallback(_agent_messages(state), tools=True)
    return {
        "messages": [response],
        "model_used": model_used,
        "rounds": state.get("rounds", 0) + 1,
    }


def _tool_call_parts(tool_call: Any) -> tuple[str, dict[str, Any], str]:
    """Normalize LangChain/Gemini tool_call objects to (name, args, id)."""
    if isinstance(tool_call, dict):
        name = str(tool_call.get("name") or "")
        args = tool_call.get("args") or {}
        call_id = str(tool_call.get("id") or "")
    else:
        name = str(getattr(tool_call, "name", "") or "")
        args = getattr(tool_call, "args", None) or {}
        call_id = str(getattr(tool_call, "id", "") or "")
    if not isinstance(args, dict):
        args = {"input": args}
    return name, args, call_id


def tools_node(state: AgentState) -> dict[str, Any]:
    """Run tool calls and append ToolMessages + structured log for the UI."""
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {}

    tools_by_name = {t.name: t for t in ANALYTICS_TOOLS}
    tool_messages: list[ToolMessage] = []
    log = list(state.get("tool_calls_log") or [])

    for tc in last.tool_calls:
        name, args, call_id = _tool_call_parts(tc)
        tool = tools_by_name.get(name)
        try:
            if tool is None:
                content = json.dumps({"error": f"Unknown tool: {name}"})
            else:
                # Invoke the tool function directly so DB errors never escape the graph.
                raw = tool.invoke(args)
                content = raw if isinstance(raw, str) else json.dumps(raw, default=str)
        except Exception as exc:
            content = json.dumps({"error": f"Tool execution failed: {exc}"})

        tm_kwargs: dict[str, Any] = {
            "content": content,
            "tool_call_id": call_id or name or "unknown",
        }
        if name:
            tm_kwargs["name"] = name
        tool_messages.append(ToolMessage(**tm_kwargs))

        entry: dict[str, Any] = {"tool": name, "args": args}
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "error" in parsed:
                entry["error"] = parsed["error"]
            else:
                entry["result"] = parsed
        except (json.JSONDecodeError, TypeError):
            entry["result"] = content
        log.append(entry)

    return {"messages": tool_messages, "tool_calls_log": log}


def verify_node(state: AgentState) -> dict[str, Any]:
    answer = _latest_ai_text(state["messages"])
    user_q = _latest_user_text(state["messages"])
    tool_log = state.get("tool_calls_log") or []
    attempts = state.get("verify_attempts", 0) + 1

    if not answer.strip():
        return {
            "verify_ok": False,
            "verify_feedback": "Your last response was empty. Use tools if needed, then provide a full answer with provenance.",
            "verify_attempts": attempts,
        }

    if VERIFY_KPI_HINT.search(user_q) and not tool_log:
        return {
            "verify_ok": False,
            "verify_feedback": (
                "This looks like a KPI/analytics question but no tools were used. "
                "Call list_metrics / run_metric (or get_domain_doc + run_sql) before answering."
            ),
            "verify_attempts": attempts,
        }

    if "Source:" not in answer:
        return {
            "verify_ok": False,
            "verify_feedback": (
                "Add the required provenance footer ending with: "
                "Source: [...] | Metric: [...] | Window: [...] | Reviewed: basic"
            ),
            "verify_attempts": attempts,
        }

    # Empty / error-only tool outcomes for run_metric / run_sql
    for entry in tool_log:
        if entry.get("tool") in {"run_metric", "run_sql"} and entry.get("error"):
            if attempts < 2:
                return {
                    "verify_ok": False,
                    "verify_feedback": (
                        f"Tool {entry['tool']} failed: {entry['error']}. "
                        "Fix arguments or try an alternate approach, then answer."
                    ),
                    "verify_attempts": attempts,
                }

    return {"verify_ok": True, "verify_feedback": "", "verify_attempts": attempts}


def answer_node(state: AgentState) -> dict[str, Any]:
    text = _latest_ai_text(state["messages"]).strip()
    model_used = state.get("model_used") or settings.gemini_model
    if model_used != settings.gemini_model and text:
        text = (
            f"_Note: using fallback model `{model_used}` "
            f"because `{settings.gemini_model}` quota was exhausted._\n\n"
            f"{text}"
        )
    if not text:
        text = "Reached maximum tool call rounds without a final answer."
    return {"final_answer": text}


def route_after_agent(state: AgentState) -> Literal["tools", "verify"]:
    last = state["messages"][-1]
    if (
        isinstance(last, AIMessage)
        and last.tool_calls
        and state.get("rounds", 0) < MAX_TOOL_ROUNDS
    ):
        return "tools"
    return "verify"


def route_after_verify(state: AgentState) -> Literal["agent", "answer"]:
    if state.get("verify_ok"):
        return "answer"
    if state.get("rounds", 0) >= MAX_TOOL_ROUNDS:
        return "answer"
    if state.get("verify_attempts", 0) >= 3:
        return "answer"
    return "agent"


def inject_feedback(state: AgentState) -> dict[str, Any]:
    """Before retrying agent after a failed verify, inject feedback."""
    feedback = state.get("verify_feedback") or ""
    if not feedback:
        return {}
    return {
        "messages": [
            HumanMessage(
                content=f"Verification failed. Please revise.\n\nFeedback: {feedback}"
            )
        ]
    }


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("verify", verify_node)
    graph.add_node("inject_feedback", inject_feedback)
    graph.add_node("answer", answer_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "verify": "verify"})
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {"agent": "inject_feedback", "answer": "answer"},
    )
    graph.add_edge("inject_feedback", "agent")
    graph.add_edge("answer", END)

    return graph.compile()


analytics_graph = build_graph()
