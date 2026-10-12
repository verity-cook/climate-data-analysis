"""One-off helper: build src/reference/continents.csv from the ISO codes in
the database. Run it from the project root:
    python -m scripts.build_continents
The CSV is then reviewed by hand and committed."""
import csv
from pathlib import Path

import pycountry_convert as pc

from src.db import get_connection

CONTINENT_NAMES = {
    "AF": "Africa",
    "AS": "Asia",
    "EU": "Europe",
    "NA": "North America",
    "SA": "South America",
    "OC": "Oceania",
}

# Fill in codes the library can't map, e.g. {"XYZ": "Europe"}
OVERRIDES: dict[str, str] = {"ATA": "Antartica",
                             "VAT": "Europe",
                             "SXM": "North America",
                             "TLS": "Asia"}

OUTPUT = Path("src/reference/continents.csv")


def continent_for(iso3: str) -> str | None:
    if iso3 in OVERRIDES:
        return OVERRIDES[iso3]
    try:
        alpha2 = pc.country_alpha3_to_country_alpha2(iso3)
        code = pc.country_alpha2_to_continent_code(alpha2)
    except (KeyError, ValueError):
        return None
    return CONTINENT_NAMES.get(code)


def main() -> None:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT iso_code, country FROM emissions_countries "
                "WHERE iso_code IS NOT NULL ORDER BY iso_code"
            )
            countries = cur.fetchall()
    finally:
        conn.close()

    rows, unmapped = [], []
    for iso, country in countries:
        continent = continent_for(iso)
        if continent:
            rows.append((iso, continent))
        else:
            unmapped.append((iso, country))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["iso_code", "continent"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} mappings to {OUTPUT}")
    print(f"Unmapped ({len(unmapped)}):")
    for iso, country in unmapped:
        print(f"  {iso}  {country}")


if __name__ == "__main__":
    main()