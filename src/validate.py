import logging
import uuid
from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.db import get_connection


log = logging.getLogger(__name__)

MIN_ROWS = 10_000

CREATE_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS data_quality_log (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL,
    checked_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    check_name  TEXT NOT NULL,
    severity    TEXT NOT NULL,
    passed      BOOLEAN NOT NULL,
    details     TEXT
);
"""

INSERT_LOG = """
INSERT INTO data_quality_log (run_id, check_name, severity, passed, details)
VALUES (%s, %s, %s, %s, %s);
"""

@dataclass
class CheckResult:
    name: str
    severity: str # "error" blocks the load, "warning" is only logged
    passed: bool
    details: str 

class DataQualityError(Exception):
    pass

def check_row_count(df: pd.DataFrame) -> CheckResult:
    n = len(df)
    return CheckResult(
        "row_count", 
        "error", 
        n >= MIN_ROWS, 
        f"{n} rows (minimum {MIN_ROWS})"
    )

def check_year_range(df: pd.DataFrame) -> CheckResult:
    this_year = date.today().year
    bad = df[(df["year"] < 1700) | (df["year"] > this_year)]
    return CheckResult(
        "year_range",
        "error",
        bad.empty,
        f"{len(bad)} rows outside 1700-{this_year}",
    )   

def check_non_negative(df: pd.DataFrame) -> CheckResult:
    counts = {c: int((df[c] < 0).sum()) for c in ['population','co2','co2_per_capita']}
    counts = {c: n for c, n in counts.items() if n}
    return CheckResult(
        f"non_negative_values",
        "error",
        not counts,
        f"negative values: {counts}" if counts else "no negative values",
    )

def check_known_countries(df: pd.DataFrame) -> CheckResult:
    expected = ["Germany", "France", "United States", "India"]
    present = set(df["country"])
    missing = [c for c in expected if c not in present]
    flagged = df.loc[
        df["country"].isin(expected) & df["is_aggregate"], "country"
    ].unique().tolist()
    return CheckResult(
        "known_countries_not_aggregate", 
        "error", 
        not missing and not flagged,
        f"missing: {missing}; wrongly flagged as aggregate: {flagged}",
    )

def check_aggregate_count(df: pd.DataFrame) -> CheckResult:
    names = set(df.loc[df["is_aggregate"], "country"])
    ok = 5 <= len(names) <= 150 and "World" in names
    return CheckResult(
        "aggregate_count", 
        "error", 
        ok,
        f"{len(names)} aggregate entities; 'World' present: {'World' in names}",
    )

def check_per_capita_consistency(df: pd.DataFrame) -> CheckResult:
    # co2 is in million tonnes, co2_per_capita in tonnes per person
    sub = df.dropna(subset=["co2", "population", "co2_per_capita"])
    sub = sub[(sub["population"] > 0) & (sub["co2_per_capita"] > 0)]
    implied = sub["co2"] * 1e6 / sub["population"]
    rel_diff = (implied - sub["co2_per_capita"]).abs() / sub["co2_per_capita"]
    share_bad = float((rel_diff > 0.10).mean()) if len(sub) else 1.0
    return CheckResult(
        "co2_per_capita_consistency", 
        "warning", 
        share_bad <= 0.01,
        f"{share_bad:.2%} of {len(sub)} rows deviate >10% from co2/population",
    )

def check_freshness(df: pd.DataFrame) -> CheckResult:
    latest = int(df["year"].max())
    return CheckResult(
        "freshness", 
        "warning", 
        latest >= date.today().year - 3,
        f"latest year in data: {latest}",
    )

CHECKS = [
    check_row_count,
    check_year_range,
    check_non_negative,
    check_known_countries,
    check_aggregate_count,
    check_per_capita_consistency,
    check_freshness,
]

def write_log(results: list[CheckResult], run_id: str) -> None:
    rows = [(run_id, r.name, r.severity, r.passed, r.details) for r in results]
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_LOG_TABLE)
                cur.executemany(INSERT_LOG, rows)
    finally:
        conn.close()

def validate(df: pd.DataFrame) -> None:
    run_id = uuid.uuid4().hex[:8]
    results = [check(df) for check in CHECKS]
    write_log(results, run_id)  # logged even if we are about to fail

    for r in results:
        if r.passed:
            level = logging.INFO
        else:
            level = logging.ERROR if r.severity == "error" else logging.WARNING
        log.log(level, "[%s] %s: %s", "PASS" if r.passed else "FAIL", r.name, r.details)

    failed = [r.name for r in results if not r.passed and r.severity == "error"]
    if failed:
        raise DataQualityError(f"Blocking checks failed: {failed}")