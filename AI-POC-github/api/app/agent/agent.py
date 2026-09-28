"""Analytics agent facade — streams LangGraph events over the existing SSE contract."""

from __future__ import annotations

from typing import Any, AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import analytics_graph
from app.agent.scope import SCOPE_REFUSAL_MESSAGE, is_out_of_scope
from app.agent.shortcuts import match_pipeline_shortcut
from app.config import settings
from app.db import WRITE_DENIED_MESSAGE, is_mutation_request


def _refusal(content: str) -> str:
    return f"{content}\n\nSource: N/A | Metric: N/A | Window: N/A | Reviewed: basic"


class AnalyticsAgent:
    def __init__(self) -> None:
        self.configured = bool(settings.gemini_api_key)
        self.graph = analytics_graph if self.configured else None

    async def chat(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        # Block write/destructive requests before any LLM or SQL execution.
        if is_mutation_request(message):
            yield {"type": "text", "content": _refusal(WRITE_DENIED_MESSAGE)}
            yield {"type": "done", "tool_calls": []}
            return

        # Loan-analytics only — block architecture, tools, and off-topic chat.
        if is_out_of_scope(message, history):
            yield {"type": "text", "content": _refusal(SCOPE_REFUSAL_MESSAGE)}
            yield {"type": "done", "tool_calls": []}
            return

        # Deterministic pipeline shortcuts (avoid LLM inventing columns like applicant_name).
        try:
            shortcut = match_pipeline_shortcut(message)
        except Exception as exc:
            yield {"type": "error", "content": f"Pipeline query failed: {exc}"}
            return

        if shortcut:
            for entry in shortcut.get("tool_calls") or []:
                yield {
                    "type": "tool",
                    "tool": entry.get("tool", "unknown"),
                    "args": entry.get("args") or {},
                }
            yield {"type": "text", "content": shortcut["answer"]}
            yield {"type": "done", "tool_calls": shortcut.get("tool_calls") or []}
            return

        if not self.configured or self.graph is None:
            yield {
                "type": "error",
                "content": "GEMINI_API_KEY is not configured. Set it in .env and restart the API.",
            }
            return

        messages: list[Any] = []
        for turn in history or []:
            if turn["role"] == "user":
                messages.append(HumanMessage(content=turn["content"]))
            elif turn["role"] == "assistant":
                messages.append(AIMessage(content=turn["content"]))
        messages.append(HumanMessage(content=message))

        initial_state = {
            "messages": messages,
            "plan": "",
            "tool_calls_log": [],
            "verify_ok": False,
            "verify_feedback": "",
            "verify_attempts": 0,
            "rounds": 0,
            "model_used": settings.gemini_model,
            "final_answer": "",
        }

        emitted_tools = 0
        plan_emitted = False
        tool_calls_log: list[dict[str, Any]] = []
        answered = False

        try:
            async for update in self.graph.astream(initial_state, stream_mode="updates"):
                for node_name, delta in update.items():
                    if not isinstance(delta, dict):
                        continue

                    if node_name == "plan" and not plan_emitted:
                        plan = delta.get("plan") or ""
                        if plan:
                            yield {"type": "tool", "tool": "plan", "args": {"plan": plan}}
                            plan_emitted = True

                    if isinstance(delta.get("tool_calls_log"), list):
                        tool_calls_log = delta["tool_calls_log"]
                        if len(tool_calls_log) > emitted_tools:
                            for entry in tool_calls_log[emitted_tools:]:
                                yield {
                                    "type": "tool",
                                    "tool": entry.get("tool", "unknown"),
                                    "args": entry.get("args") or {},
                                }
                            emitted_tools = len(tool_calls_log)

                    if node_name == "answer":
                        final = delta.get("final_answer") or ""
                        yield {"type": "text", "content": final}
                        yield {"type": "done", "tool_calls": tool_calls_log}
                        answered = True

            if not answered:
                yield {
                    "type": "text",
                    "content": "Agent finished without a final answer.",
                }
                yield {"type": "done", "tool_calls": tool_calls_log}
        except Exception as exc:
            yield {"type": "error", "content": f"LangGraph agent error: {exc}"}
