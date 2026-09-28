"""Deterministic answers for high-traffic pipeline questions.

Bypasses LLM SQL generation for known intents so demos stay reliable.
"""

from __future__ import annotations

import re
from typing import Any

from app.agent import tools

# Snapshot window used when metric APIs require dates (templates ignore them).
_SNAPSHOT_START = "2025-01-01"
_SNAPSHOT_END = "2025-08-31"

_CM_MORE_INFO = re.compile(
    r"\b(cm\s*review|under\s*cm\s*review).{0,40}\bmore\s*info\b"
    r"|\bmore\s*info.{0,40}\b(cm\s*review|required)\b",
    re.IGNORECASE | re.DOTALL,
)

_UNDER_CM = re.compile(
    r"\b(under\s*cm\s*review|cm\s*review)\b",
    re.IGNORECASE,
)

# Columns the model often invents that do not exist on application.
_HALLUCINATED = (
    r"applicant_name|customer_name|student_name|borrower_name|full_name"
)
HALLUCINATED_COLUMNS = re.compile(rf"\b(?:a\.)?(?:{_HALLUCINATED})\b", re.IGNORECASE)

SAFE_LISTING_SQL = """
SELECT a.application_id, a.loan_id, a.branch_location, a.institute_name,
       a.credit_manager, c.more_info_required_status, c.more_info_required_date
FROM application a
JOIN credit_history c ON a.loan_id = c.loan_id
WHERE a.status = 'under_cm_review'
  AND c.more_info_required_status IS NOT NULL
ORDER BY c.more_info_required_date NULLS LAST
""".strip()


def sanitize_sql(sql: str) -> tuple[str, list[str]]:
    """Replace known hallucinated columns with institute_name; return warnings."""
    warnings: list[str] = []
    if HALLUCINATED_COLUMNS.search(sql):
        warnings.append(
            "Replaced non-existent name column(s) with institute_name "
            "(application has no applicant_name)."
        )
        sql = re.sub(
            rf"\ba\.(?:{_HALLUCINATED})\b",
            "a.institute_name",
            sql,
            flags=re.IGNORECASE,
        )
        sql = re.sub(
            rf"\b(?:{_HALLUCINATED})\b",
            "institute_name",
            sql,
            flags=re.IGNORECASE,
        )
    return sql, warnings


def match_pipeline_shortcut(message: str) -> dict[str, Any] | None:
    """If the question matches a known pipeline snapshot, return a ready answer payload."""
    q = (message or "").strip()
    if not q:
        return None

    if _CM_MORE_INFO.search(q):
        return _run_snapshot(
            metric_name="CM Review More Info Required",
            label="applications under CM review with more info required",
            include_sample=True,
        )

    if _UNDER_CM.search(q) and "more info" not in q.lower():
        return _run_snapshot(
            metric_name="Under CM Review",
            label="applications currently under CM review",
            include_sample=False,
        )

    return None


def _run_snapshot(
    *,
    metric_name: str,
    label: str,
    include_sample: bool,
) -> dict[str, Any]:
    result = tools.run_metric(metric_name, _SNAPSHOT_START, _SNAPSHOT_END)
    value = result.get("value", 0)
    tool_calls: list[dict[str, Any]] = [
        {
            "tool": "run_metric",
            "args": {
                "name": metric_name,
                "start_date": _SNAPSHOT_START,
                "end_date": _SNAPSHOT_END,
            },
            "result": result,
        }
    ]

    sample_note = ""
    if include_sample and int(value or 0) > 0:
        from app.db import run_query

        rows = run_query(SAFE_LISTING_SQL)
        tool_calls.append(
            {
                "tool": "run_sql",
                "args": {"sql": SAFE_LISTING_SQL},
                "result": rows[:10],
            }
        )
        if rows:
            lines = [
                f"- loan_id={r.get('loan_id')} | branch={r.get('branch_location')} | "
                f"institute={r.get('institute_name')} | status={r.get('more_info_required_status')}"
                for r in rows[:8]
            ]
            sample_note = "\n\nSample applications:\n" + "\n".join(lines)

    answer = (
        f"There are **{value}** {label}.{sample_note}\n\n"
        f"Source: semantic_metric | Metric: {metric_name} | "
        f"Window: snapshot (current pipeline) | Reviewed: basic"
    )
    return {"answer": answer, "tool_calls": tool_calls}
