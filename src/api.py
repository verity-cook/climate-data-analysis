from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from psycopg2.extras import RealDictCursor

from src.db import get_connection

app = FastAPI(
    title="Climate Data API", 
    description="Read-only access to validated CO2 emission data" 
    "(source: Our World in Data, CC BY 4.0)",
    version="0.1.0",
)

def query(sql: str, params: list | tuple = ()) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/health")
def health():
    query("SELECT 1") # fails if database is not reachable
    return {"status": "ok"}

@app.get("/countries")
def list_countries():
    sql = "SELECT DISTINCT country, iso_code FROM emissions_countries ORDER BY country"
    return query(sql)

@app.get("/aggregates")
def list_aggregates():
    sql = "SELECT DISTINCT country FROM emissions_aggregates ORDER BY country"
    return query(sql)

@app.get("/emissions/{entity}")
def get_emissions(
    entity: str,
    start_year: int | None = Query(None, ge=1700, le=2100),
    end_year: int | None = Query(None, ge=1700, le=2100),
):
    sql = """
        SELECT country, year, iso_code, population, gdp, co2, co2_per_capita, total_ghg, is_aggregate
        FROM emissions
        WHERE country = %s
    """
    params: list = [entity]
    if start_year is not None:
        sql += " AND year >= %s"
        params.append(start_year)
    if end_year is not None:
        sql += " AND year <= %s"
        params.append(end_year)
    sql += " ORDER BY year"

    rows = query(sql, params)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data found for {entity}")

    return rows

@app.get("/quality/latest")
def get_latest_quality():
    sql = """
        SELECT * FROM data_quality_log
        WHERE run_id = (SELECT run_id FROM data_quality_log ORDER BY id DESC LIMIT 1) 
        ORDER BY id
    """
    return query(sql)

INTL_TRANSPORT = "International aviation"
INTL_SHIPPING = "International shipping"


@app.get("/shares")
def get_shares(year: int | None = Query(None, ge=1750, le=2100)):
    if year is None:
        latest = query(
            "SELECT max(year) AS year FROM emissions_aggregates "
            "WHERE country = 'World' AND co2 IS NOT NULL"
        )
        year = latest[0]["year"]
        if year is None:
            raise HTTPException(status_code=404, detail="No world totals available")

    aggregates = query(
        "SELECT country, co2 FROM emissions_aggregates "
        "WHERE year = %s AND country IN ('World', %s, %s) AND co2 IS NOT NULL",
        (year, INTL_TRANSPORT, INTL_SHIPPING),
    )
    totals = {r["country"]: r["co2"] for r in aggregates}
    world = totals.get("World")
    if world is None:
        raise HTTPException(status_code=404, detail=f"No world total for {year}")

    rows = query(
        "SELECT COALESCE(cc.continent, 'Unassigned') AS continent, "
        "e.country, e.iso_code, e.co2 "
        "FROM emissions_countries e "
        "LEFT JOIN country_continent cc ON cc.iso_code = e.iso_code "
        "WHERE e.year = %s AND e.co2 > 0 "
        "ORDER BY e.co2 DESC",
        (year,),
    )

    continents: dict[str, dict] = {}
    for r in rows:
        group = continents.setdefault(
            r["continent"], {"name": r["continent"], "value": 0.0, "countries": []}
        )
        group["value"] += r["co2"]
        group["countries"].append(
            {"name": r["country"], "iso_code": r["iso_code"], "value": r["co2"]}
        )
    ordered = sorted(continents.values(), key=lambda c: c["value"], reverse=True)

    transport = totals.get(INTL_TRANSPORT, 0.0)
    shipping = totals.get(INTL_SHIPPING, 0.0)
    allocated = sum(c["value"] for c in ordered) + transport + shipping
    return {
        "year": year,
        "world_total": world,
        "continents": ordered,
        "international_transport": transport,
        "international_shipping": shipping,
        "unallocated": world - allocated,
    }

app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="static",
)