import re
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from app.config import settings

ALLOWED_TABLES = {
    "application",
    "disbursement",
    "credit_history",
    "dim_date",
    "semantic.metric",
    "semantic.metric_dimension",
    "semantic.domain_doc",
}

BLOCKED_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY)\b",
    re.IGNORECASE,
)

WRITE_DENIED_MESSAGE = (
    "This assistant is read-only. It can query and analyze loan analytics data, "
    "but it cannot insert, update, delete, drop, or otherwise modify tables or records. "
    "Please rephrase as a read-only analytics question, or use a database admin tool for changes."
)

# Natural-language requests that ask to mutate data/schema (not analytics about "updated" apps).
MUTATION_INTENT = re.compile(
    r"(?:"
    r"\b(?:delete|drop|truncate|remove)\b.{0,48}\b(?:table|tables|schema|database|records?|rows?|data)\b"
    r"|"
    r"\b(?:delete|drop|truncate)\s+from\b"
    r"|"
    r"\bupdate\b.{0,80}\bset\b"
    r"|"
    r"\binsert\s+into\b"
    r"|"
    r"\balter\s+table\b"
    r"|"
    r"\bcreate\s+(?:table|index|view|schema)\b"
    r"|"
    r"\b(?:wipe|destroy|purge)\b.{0,48}\b(?:table|tables|database|data|records?)\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)


def is_mutation_request(text: str) -> bool:
    """True when the user is asking to modify or destroy data/schema."""
    return bool(MUTATION_INTENT.search(text or ""))


@contextmanager
def get_connection():
    conn = psycopg2.connect(settings.database_url)
    try:
        yield conn
    finally:
        conn.close()


def run_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    # Normalize :name placeholders to psycopg2 %(name)s style
    if params:
        for key in params:
            sql = sql.replace(f":{key}", f"%({key})s")
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SET statement_timeout = {settings.sql_timeout_ms}")
            # Only pass params when present. Passing {} makes psycopg2 parse %-escapes
            # and raises "dict is not a sequence" for LIKE '%...%' or positional %s.
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            rows = cur.fetchmany(settings.sql_row_limit)
            return [dict(row) for row in rows]


def validate_readonly_sql(sql: str) -> None:
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise ValueError(
            "Multiple SQL statements are not allowed. Ask one read-only analytics question at a time."
        )
    if BLOCKED_SQL.search(stripped):
        raise ValueError(WRITE_DENIED_MESSAGE)
    if not re.match(r"^\s*SELECT\b", stripped, re.IGNORECASE):
        raise ValueError(
            "Only SELECT queries are allowed. This assistant cannot modify data or schema."
        )


def list_tables() -> list[str]:
    sql = """
    SELECT table_schema || '.' || table_name AS full_name
    FROM information_schema.tables
    WHERE table_schema IN ('public', 'semantic')
      AND table_type = 'BASE TABLE'
    ORDER BY 1
    """
    rows = run_query(sql)
    allowed_names = {t.split(".")[-1] for t in ALLOWED_TABLES}
    return [
        r["full_name"]
        for r in rows
        if r["full_name"] in ALLOWED_TABLES or r["full_name"].split(".")[-1] in allowed_names
    ]


def _resolve_table_name(table_name: str) -> tuple[str, str]:
    normalized = table_name.strip()
    allowed_bases = {t.split(".")[-1] for t in ALLOWED_TABLES}
    base_name = normalized.split(".")[-1]

    if normalized not in ALLOWED_TABLES and base_name not in allowed_bases:
        raise ValueError(f"Table not allowed: {table_name}")

    if "." in normalized:
        schema, name = normalized.split(".", 1)
        return schema, name
    return "public", normalized


def describe_table(table_name: str) -> list[dict[str, Any]]:
    schema, name = _resolve_table_name(table_name)

    sql = """
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = %(schema)s AND table_name = %(name)s
    ORDER BY ordinal_position
    """
    return run_query(sql, {"schema": schema, "name": name})
