import pandas as pd
import pytest

from src import validate as v

COUNTRIES = ["Germany", "France", "United States", "India"]
AGGREGATES = [
    "World", "Africa (GCP)", "Europe (GCP)", "Asia (GCP)", "North America (GCP)",
]

def make_row(country, year=2022, aggregate=False, population=1_000_000.0, per_capita=5.0):
    return {
        "country": country,
        "year": year,
        "iso_code": None if aggregate else country[:3].upper(),
        "population": population,
        "gdp": 1e9,
        "co2": per_capita * population / 1e6,  # million tonnes
        "co2_per_capita": per_capita,          # tonnes per person
        "total_ghg": 10.0,
        "is_aggregate": aggregate,
    }

@pytest.fixture
def good_df(): # build a good dataframe for every test that asks
    rows = [make_row(country) for country in COUNTRIES]
    rows += [make_row(aggregate, aggregate=True) for aggregate in AGGREGATES]
    return pd.DataFrame(rows)

@pytest.fixture
def no_db(monkeypatch):
    """Stop validate() from writing to the real quality log table."""
    monkeypatch.setattr(v, "write_log", lambda results, run_id: None)

def test_row_count_passes_when_threshold_met(good_df, monkeypatch):
    monkeypatch.setattr(v, "MIN_ROWS", 5)
    assert v.check_row_count(good_df).passed

def test_row_count_fails_on_small_frame(good_df):
    assert not v.check_row_count(good_df).passed

def test_year_range_passes_on_good_data(good_df):
    assert v.check_year_range(good_df).passed

def test_year_range_fails_on_impossible_year(good_df):
    good_df.loc[0, "year"] = 1500
    assert not v.check_year_range(good_df).passed

def test_non_negative_passes_on_good_data(good_df):
    assert v.check_non_negative(good_df).passed

def test_non_negative_fails_on_negative_co2(good_df):
    good_df.loc[0, "co2"] = -5.0
    result = v.check_non_negative(good_df)
    assert not result.passed
    assert "co2" in result.details

def test_known_countries_fails_when_country_missing(good_df):
    df = good_df[good_df["country"] != "Germany"]
    assert not v.check_known_countries(df).passed

def test_known_countries_fails_when_country_flagged_as_aggregate(good_df):
    good_df.loc[good_df["country"] == "Germany", "is_aggregate"] = True
    assert not v.check_known_countries(good_df).passed

def test_aggregate_count_fails_without_world(good_df):
    df = good_df[good_df["country"] != "World"]
    assert not v.check_aggregate_count(df).passed

def test_per_capita_consistency_passes_on_good_data(good_df):
    assert v.check_per_capita_consistency(good_df).passed

def test_per_capita_consistency_fails_on_inconsistent_values(good_df):
    good_df.loc[good_df["country"] == "Germany", "co2"] *= 3
    assert not v.check_per_capita_consistency(good_df).passed

def test_freshness_warns_on_stale_data(good_df):
    good_df["year"] = 2000
    result = v.check_freshness(good_df)
    assert not result.passed
    assert result.severity == "warning"

def test_validate_raises_when_blocking_check_fails(good_df, no_db):
    good_df.loc[0, "co2"] = -5.0
    with pytest.raises(v.DataQualityError):
        v.validate(good_df)

def test_validate_does_not_raise_on_warning_only(good_df, no_db, monkeypatch):
    monkeypatch.setattr(v, "MIN_ROWS", 5)
    good_df["year"] = 2000  # stale data triggers a warning, not an error
    v.validate(good_df)  # should not raise