import pytest
from fastapi.testclient import TestClient

from src import api

client = TestClient(api.app)

GERMANY_ROWS = [
    {'country': 'Germany', 'year': 2020, 'iso_code': 'DEU', 'population': 83166711, 'gdp': 3806060000000.0, 'co2': 729000000.0, 'co2_per_capita': 8.76, 'total_ghg': 905000000.0, 'is_aggregate': False},
    {'country': 'Germany', 'year': 2021, 'iso_code': 'DEU', 'population': 83240525, 'gdp': 4200000000000.0, 'co2': 750000000.0, 'co2_per_capita': 9.01, 'total_ghg': 920000000.0, 'is_aggregate': False},
]

@pytest.fixture()
def fake_query(monkeypatch):
    """replace database query with fake that records its calls"""
    calls = []

    def install(rows):
        def fake(sql, params=()):
            calls.append((sql, list(params)))
            return rows

        monkeypatch.setattr(api, "query", fake)
        return calls

    return install

def test_health_ok(fake_query):
    fake_query([{"?column?": 1}])
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_countries_returns_rows(fake_query):
    rows = [{'country': row['country'], 
            'iso_code': row['iso_code']} for row in GERMANY_ROWS]
    fake_query(rows)
    response = client.get("/countries")
    assert response.status_code == 200
    assert response.json() == rows

def test_aggregates_reads_from_aggregate_view(fake_query):
    calls = fake_query([{"country": "World"}])
    response = client.get("/aggregates")
    assert response.status_code == 200
    assert response.json() == [{"country": "World"}]
    assert "emissions_aggregates" in calls[0][0]

def test_emissions_returns_rows(fake_query):
    calls = fake_query(GERMANY_ROWS)
    response = client.get("/emissions/Germany")
    assert response.status_code == 200
    assert response.json() == GERMANY_ROWS
    assert calls[0][1] == ["Germany"]

def test_emissions_year_filters_are_passed_as_parameters(fake_query):
    calls = fake_query(GERMANY_ROWS)
    client.get("/emissions/Germany?start_year=2015&end_year=2021")
    sql, params = calls[0]
    assert params == ["Germany", 2015, 2021]
    assert "year >=" in sql and "year <=" in sql

def test_emissions_handles_names_with_spaces_and_brackets(fake_query):
    calls = fake_query([{"country": "Africa (GCP)", "year": 2022}])
    response = client.get("/emissions/Africa (GCP)")
    assert response.status_code == 200
    assert calls[0][1] == ["Africa (GCP)"]

def test_emissions_unknown_entity_returns_404(fake_query):
    fake_query([])
    response = client.get("/emissions/Atlantis")
    assert response.status_code == 404

@pytest.mark.parametrize("year", [1200, 2500])
def test_emissions_rejects_out_of_range_year(fake_query, year):
    calls = fake_query(GERMANY_ROWS)
    response = client.get(f"/emissions/Germany?start_year={year}")
    assert response.status_code == 422
    assert calls == []  # validation fails before any query runs

def test_emissions_input_never_ends_up_in_sql_text(fake_query):
    calls = fake_query(GERMANY_ROWS)
    sabotage = "x'; DROP TABLE emissions; --" # input should pass as parameter
    client.get("/emissions/" + sabotage)
    sql, params = calls[0]
    assert sabotage not in sql
    assert params == [sabotage]

def test_quality_latest_returns_rows(fake_query):
    rows = [{"check_name": "row_count", "passed": True}]
    fake_query(rows)
    response = client.get("/quality/latest")
    assert response.status_code == 200
    assert response.json() == rows