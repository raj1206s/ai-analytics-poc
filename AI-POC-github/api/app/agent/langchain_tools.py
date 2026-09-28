"""LangChain tool wrappers around existing analytics helpers."""

from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.tools import tool

from app.agent import tools
from app.agent.shortcuts import sanitize_sql
from app.db import describe_table, list_tables, run_query, validate_readonly_sql


def _json(value: Any) -> str:
    return json.dumps(value, default=str)


@tool
def list_metrics(query: Optional[str] = None) -> str:
    """Search governed semantic metrics aligned with Power BI DAX measures."""
    return _json(tools.list_metrics(query or None))


@tool
def get_metric(name: str) -> str:
    """Get full definition of a governed metric including DAX source and SQL template."""
    metric = tools.get_metric(name)
    if metric is None:
        return _json({"error": f"Metric not found: {name}"})
    return _json(metric)


@tool
def run_metric(
    name: str,
    start_date: str,
    end_date: str,
    group_by: Optional[str] = None,
) -> str:
    """Execute a governed metric for a date range. Prefer this over raw SQL."""
    try:
        return _json(tools.run_metric(name, start_date, end_date, group_by))
    except Exception as exc:
        return _json({"error": str(exc)})


@tool
def get_domain_doc(domain: str) -> str:
    """Load domain reference documentation (application, credit_history, disbursement, metrics, loan_analytics)."""
    try:
        return tools.get_domain_doc(domain)
    except ValueError as exc:
        return _json({"error": str(exc)})


@tool("list_tables")
def list_tables_tool() -> str:
    """List available database tables."""
    return _json(list_tables())


@tool("describe_table")
def describe_table_tool(table_name: str) -> str:
    """Describe columns of an allowed table."""
    try:
        return _json(describe_table(table_name))
    except ValueError as exc:
        return _json({"error": str(exc)})


@tool
def run_sql(sql: str) -> str:
    """Execute a read-only SELECT query only. Never use for INSERT/UPDATE/DELETE/DROP.
    application has NO applicant_name — use loan_id, application_id, institute_name.
    """
    try:
        validate_readonly_sql(sql)
        safe_sql, warnings = sanitize_sql(sql)
        rows = run_query(safe_sql)
        if warnings:
            return _json({"rows": rows, "warnings": warnings, "sql_executed": safe_sql})
        return _json(rows)
    except Exception as exc:
        return _json(
            {
                "error": f"SQL execution failed: {exc}",
                "hint": (
                    "Use only real columns. application has no applicant_name — "
                    "prefer run_metric 'CM Review More Info Required' for CM/more-info questions, "
                    "or select loan_id, application_id, institute_name, branch_location."
                ),
            }
        )


ANALYTICS_TOOLS = [
    list_metrics,
    get_metric,
    run_metric,
    get_domain_doc,
    list_tables_tool,
    describe_table_tool,
    run_sql,
]
