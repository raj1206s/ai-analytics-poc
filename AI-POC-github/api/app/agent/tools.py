import json
from pathlib import Path
from typing import Any

from app.db import run_query

SKILLS_DIR = Path(__file__).parent.parent / "skills"

DISBURSEMENT_METRICS = {
    "First Disbursed (All)",
    "First Disbursed Amount (All)",
}


def list_metrics(query: str | None = None) -> list[dict[str, Any]]:
    sql = """
    SELECT metric_id, name, alias, description, time_axis, grain
    FROM semantic.metric
    WHERE is_active = TRUE
    """
    params: dict[str, Any] = {}
    if query:
        sql += " AND (name ILIKE %(q)s OR alias ILIKE %(q)s OR description ILIKE %(q)s)"
        params["q"] = f"%{query}%"
    sql += " ORDER BY metric_id"
    return run_query(sql, params)


def get_metric(name: str) -> dict[str, Any] | None:
    rows = run_query(
        """
        SELECT m.*,
               COALESCE(
                 json_agg(
                   json_build_object('dim_name', d.dim_name, 'column_expr', d.column_expr, 'description', d.description)
                 ) FILTER (WHERE d.dim_name IS NOT NULL),
                 '[]'
               ) AS dimensions
        FROM semantic.metric m
        LEFT JOIN semantic.metric_dimension d ON m.metric_id = d.metric_id
        WHERE m.name ILIKE %(name)s AND m.is_active = TRUE
        GROUP BY m.metric_id
        """,
        {"name": name},
    )
    if not rows:
        return None
    row = rows[0]
    dims = row.get("dimensions")
    if isinstance(dims, str):
        row["dimensions"] = json.loads(dims)
    elif dims is None:
        row["dimensions"] = []
    return row


def _build_metric_sql(metric: dict[str, Any], group_by: str | None) -> str:
    template = metric["sql_template"]
    name = metric["name"]

    if group_by:
        dim_map = {d["dim_name"]: d["column_expr"] for d in metric.get("dimensions", []) if isinstance(d, dict)}
        if group_by not in dim_map:
            dims = [d["dim_name"] for d in metric.get("dimensions", []) if isinstance(d, dict)]
            raise ValueError(f"Invalid group_by '{group_by}'. Allowed: {dims}")

        col = dim_map[group_by]
        if name in DISBURSEMENT_METRICS:
            template = template.replace(
                "FROM disbursement d",
                "FROM disbursement d JOIN application a ON d.application_id = a.application_id",
            )
            select_expr = f"{col} AS {group_by}, "
            if "COUNT(DISTINCT" in template:
                template = template.replace("SELECT COUNT(DISTINCT", f"SELECT {select_expr}COUNT(DISTINCT")
            else:
                template = template.replace("SELECT COALESCE(SUM", f"SELECT {col} AS {group_by}, COALESCE(SUM")
            template = template.replace("{{GROUP_BY}}", f"GROUP BY {col} ORDER BY {col}")
        else:
            select_expr = f"{col} AS {group_by}, "
            if "COUNT(DISTINCT" in template:
                template = template.replace("SELECT COUNT(DISTINCT", f"SELECT {select_expr}COUNT(DISTINCT")
            else:
                template = template.replace("SELECT COALESCE(SUM", f"SELECT {col} AS {group_by}, COALESCE(SUM")
            template = template.replace("{{GROUP_BY}}", f"GROUP BY {col} ORDER BY {col}")
    else:
        template = template.replace("{{GROUP_BY}}", "")

    return template.strip()


def run_metric(
    name: str,
    start_date: str,
    end_date: str,
    group_by: str | None = None,
) -> dict[str, Any]:
    metric = get_metric(name)
    if not metric:
        raise ValueError(f"Metric not found: {name}")

    sql = _build_metric_sql(metric, group_by)
    rows = run_query(sql, {"start_date": start_date, "end_date": end_date})

    if group_by:
        return {
            "metric": name,
            "start_date": start_date,
            "end_date": end_date,
            "group_by": group_by,
            "rows": rows,
            "sql_executed": sql,
        }

    value = rows[0]["value"] if rows else 0
    return {
        "metric": name,
        "start_date": start_date,
        "end_date": end_date,
        "value": value,
        "sql_executed": sql,
    }


def get_domain_doc(domain: str) -> str:
    # Prefer on-disk skills (source of truth) so doc fixes apply without DB re-seed.
    file_map = {
        "loan_analytics": SKILLS_DIR / "loan_analytics.md",
        "application": SKILLS_DIR / "references" / "application.md",
        "credit_history": SKILLS_DIR / "references" / "credit_history.md",
        "disbursement": SKILLS_DIR / "references" / "disbursement.md",
        "metrics": SKILLS_DIR / "references" / "metrics.md",
    }
    path = file_map.get(domain)
    if path and path.exists():
        return path.read_text(encoding="utf-8")

    rows = run_query(
        "SELECT markdown FROM semantic.domain_doc WHERE domain = %(domain)s",
        {"domain": domain},
    )
    if rows:
        return rows[0]["markdown"]
    raise ValueError(f"Domain doc not found: {domain}")
