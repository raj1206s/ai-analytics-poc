"""Offline eval runner for seed-pinned metric and SQL checks."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.tools import run_metric
from app.db import run_query

EVALS_PATH = Path(__file__).parent / "questions.json"


def run_evals() -> int:
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://analytics:analytics@localhost:5432/loan_analytics"
    )
    os.environ["DATABASE_URL"] = database_url

    cases = json.loads(EVALS_PATH.read_text(encoding="utf-8"))
    passed = 0
    failed = 0

    for case in cases:
        case_id = case["id"]
        try:
            if "metric" in case:
                result = run_metric(
                    case["metric"],
                    case["start_date"],
                    case["end_date"],
                    case.get("group_by"),
                )
                if case.get("group_by"):
                    rows = result.get("rows", [])
                    ok = len(rows) >= case.get("expected_min_rows", 1)
                else:
                    ok = result.get("value", 0) >= case.get("expected_min", 0)
            elif "sql" in case:
                rows = run_query(case["sql"])
                value = rows[0]["value"] if rows else 0
                ok = value >= case.get("expected_min", 0)
            else:
                ok = False

            if ok:
                passed += 1
                print(f"PASS  {case_id}")
            else:
                failed += 1
                print(f"FAIL  {case_id}")
        except Exception as exc:
            failed += 1
            print(f"ERROR {case_id}: {exc}")

    print(f"\n{passed} passed, {failed} failed out of {len(cases)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_evals())
