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


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="static",
)