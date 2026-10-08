import io
import logging

import pandas as pd
from psycopg2.extras import execute_values

from src import config
from src.extract import s3_client
from src.db import get_connection
from src.validate import validate

log = logging.getLogger(__name__)

# source columns
COLUMNS = ["country", "year", "iso_code", "population", 
           "gdp", "co2", "co2_per_capita", "total_ghg"
           ]

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS emissions (
    country TEXT NOT NULL,
    year INT NOT NULL,
    iso_code TEXT,
    population DOUBLE PRECISION,
    gdp DOUBLE PRECISION,
    co2 DOUBLE PRECISION,
    co2_per_capita DOUBLE PRECISION,
    total_ghg DOUBLE PRECISION,
    is_aggregate BOOLEAN NOT NULL DEFAULT FALSE,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (country, year)
);
"""

# added is_aggreate column after table already exists
ADD_COLUMN = """
ALTER TABLE emissions 
    ADD COLUMN IF NOT EXISTS is_aggregate BOOLEAN NOT NULL DEFAULT FALSE;
"""

CREATE_VIEWS = """
CREATE OR REPLACE VIEW emissions_countries AS
    SELECT * FROM emissions WHERE NOT is_aggregate;

CREATE OR REPLACE VIEW emissions_aggregates AS
    SELECT * FROM emissions WHERE is_aggregate;
"""

UPSERT = """
INSERT INTO emissions 
    (country, year, iso_code, population, gdp, co2, co2_per_capita, 
    total_ghg, is_aggregate)
VALUES %s
ON CONFLICT (country, year) DO UPDATE SET
    iso_code = EXCLUDED.iso_code,
    population = EXCLUDED.population,
    gdp = EXCLUDED.gdp,
    co2 = EXCLUDED.co2,
    co2_per_capita = EXCLUDED.co2_per_capita,
    total_ghg = EXCLUDED.total_ghg,
    is_aggregate = EXCLUDED.is_aggregate,
    loaded_at = NOW();
"""

def read_latest_raw() -> pd.DataFrame:
    s3 = s3_client()
    listing = s3.list_objects_v2(Bucket=config.RAW_BUCKET, Prefix="raw/")
    keys = [obj["Key"] for obj in listing.get("Contents", [])]
    if not keys:
        raise RuntimeError("No raw files found - run src.extract first")
    key = max(keys) #max is most recent because of ISO date format
    log.info("Reading s3://%s/%s", config.RAW_BUCKET, key)
    body = s3.get_object(Bucket=config.RAW_BUCKET, Key=key)["Body"].read()
    return pd.read_csv(io.BytesIO(body))

def clean(df: pd.DataFrame) -> pd.DataFrame:
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Columns missing from source: {sorted(missing)}")
    df = df[COLUMNS].copy()
    df = df.dropna(subset=["country", "year"])
    df["year"] = df["year"].astype(int)
    df = df.drop_duplicates(subset=["country", "year"], keep="last")
    df["is_aggregate"] = df["iso_code"].isna()
    return df

def load(df: pd.DataFrame) -> None:
    # Postgres needs None, not NaN, for missing values
    rows = list(
        df.astype(object).where(df.notna(), None).itertuples(index=False, name = None)
    )
    conn = get_connection()

    try:
        with conn: # commits on success, rolls back on exception, prevent half loaded table
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE)
                cur.execute(ADD_COLUMN)
                execute_values(cur, UPSERT, rows, page_size=1000)
                cur.execute(CREATE_VIEWS)
    finally:
        conn.close()


def run() -> None:
    df = clean(read_latest_raw())
    validate(df) # raises if a blocking check fails
    load(df)
    log.info("Loaded %d rows into emissions", len(df))

if __name__ == "__main__":
    run()