"""Scope guard: loan analytics questions only.

Blocks architecture/tool introspection and general off-topic chat.
"""

from __future__ import annotations

import re

SCOPE_REFUSAL_MESSAGE = (
    "I'm here to help with loan analytics only — for example logins, sanctions, "
    "disbursements, pipeline status, and related metrics or reports. "
    "I can't answer questions about system architecture, internal tools, or other topics. "
    "Please ask an analytics question about your loan data."
)

# Loan / KPI / data analytics vocabulary used by this POC.
_ANALYTICS_SCOPE = re.compile(
    r"\b("
    r"login|logins|sanction|sanctions|disburs|disbursement|disbursements|"
    r"metric|metrics|kpi|kpis|pipeline|branch|branches|"
    r"application|applications|credit[_\s-]?history|loan|loans|"
    r"amount|count|mtd|ytd|q[1-4]|quarter|fy\d{2,4}|"
    r"cm\s*review|declined|under\s*review|more\s+info|"
    r"dax|power\s*bi|semantic|governed|"
    r"analytics|report|dashboard|trend|trends|"
    r"table|tables|column|columns|schema|data\s*model|"
    r"select|sql|query|queries|join|"
    r"list_metrics|run_metric|run_sql|describe_table|list_tables|get_domain_doc|"
    r"asia/?kolkata|date\s*range|start_date|end_date|"
    r"march|april|may|june|july|august|september|october|november|december|"
    r"january|february|20\d{2}"
    r")\b",
    re.IGNORECASE,
)

# Architecture / agent-internals / tool-introspection — always refused.
_BLOCKED_SYSTEM = re.compile(
    r"(?:"
    r"\b("
    r"architecture|langgraph|langchain|gemini|google\s*genai|"
    r"tool\s*node|agent\s*graph|system\s*prompt|provenance|"
    r"fastapi|sse|streaming|tech\s*stack|codebase|source\s*code|"
    r"internal\s+tools?|how\s+you\s+(work|are\s+built|were\s+built)"
    r")\b"
    r"|"
    r"\bhow\s+(does|do|is)\s+(this|the)\s+(system|agent|poc|assistant)\b"
    r"|"
    r"\bwhat\s+(tools?|models?|llm|ai)\s+(does|do|are|have|can)\b"
    r"|"
    r"\bwhich\s+(tools?|models?|llm|ai)\b"
    r"|"
    r"\b(show|list|explain|describe)\s+(me\s+)?(your|the)\s+(tools?|architecture|prompts?)\b"
    r"|"
    r"\b(tell\s+me\s+about|explain)\s+(your|the)\s+(architecture|tools?|stack)\b"
    r")",
    re.IGNORECASE,
)

# Clearly general-purpose / off-topic / casual / unsafe intents.
_OUT_OF_SCOPE = re.compile(
    r"(?:"
    r"\b("
    r"weather|recipe|cook|poem|joke|story|lyrics|horoscope|"
    r"capital\s+of|who\s+is\s+the\s+president|translate|"
    r"homework|essay|resume|cover\s+letter|"
    r"crypto|bitcoin|stock\s+pick|dating|relationship|"
    r"medical\s+advice|diagnose|prescription|"
    r"write\s+(me\s+)?(a\s+)?(python|java|c\+\+|javascript)\s+(script|code|program)|"
    r"generate\s+(an?\s+)?image|draw\s+(me\s+)?a|"
    r"play\s+(a\s+)?game|trivia|"
    r"i\s+love\s+you|love\s+you|i\s+hate\s+you|hate\s+you|"
    r"i\s+kill\s+you|kill\s+you|murder|suicide|"
    r"marry\s+me|will\s+you\s+be\s+my|"
    r"who\s+are\s+you|what\s+are\s+you|are\s+you\s+(a\s+)?(bot|ai|human)|"
    r"sing\s+(me\s+)?(a\s+)?song|tell\s+me\s+a\s+joke"
    r")\b"
    r"|"
    r"^(hi|hello|hey|good\s+(morning|afternoon|evening)|thanks|thank\s+you|"
    r"bye|goodbye|ok|okay|cool|nice|great|wow|lol|haha)[.!?\s]*$"
    r")",
    re.IGNORECASE,
)


def is_in_scope(text: str) -> bool:
    """True when the question is about loan analytics data / metrics."""
    q = (text or "").strip()
    if not q:
        return False
    if _BLOCKED_SYSTEM.search(q):
        return False
    return bool(_ANALYTICS_SCOPE.search(q))


def is_out_of_scope(
    text: str,
    history: list[dict[str, str]] | None = None,
) -> bool:
    """True when the question is outside loan-analytics scope.

    Short follow-ups are allowed when recent chat history is already in scope,
    unless the message is clearly blocked (architecture/tools/off-topic).
    """
    q = (text or "").strip()
    if not q:
        return True
    if _BLOCKED_SYSTEM.search(q):
        return True
    if _OUT_OF_SCOPE.search(q):
        return True
    if is_in_scope(q):
        return False
    # Allow brief follow-ups (e.g. "by branch") when prior turns were in scope.
    if history and len(q.split()) <= 12:
        recent = " ".join(
            str(turn.get("content") or "")
            for turn in history[-6:]
            if turn.get("role") in {"user", "assistant"}
        )
        if is_in_scope(recent):
            return False
    return True
