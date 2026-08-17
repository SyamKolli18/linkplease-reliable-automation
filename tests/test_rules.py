"""Tests for Rule creation and keyword matching logic."""

from app.services.rule_engine import match_rules
from app.models.rule import Rule


def test_create_rule(client):
    payload = {
        "keyword": "PRICE",
        "dm_message": "Here is the price list: https://example.com/pricing"
    }
    response = client.post("/rules", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "rule_id" in data
    assert data["keyword"] == "PRICE"
    assert data["dm_message"] == payload["dm_message"]


def test_rule_matching_case_insensitive(db_session):
    rule1 = Rule(keyword="PRICE", dm_message="Price message")
    rule2 = Rule(keyword="info", dm_message="Info message")
    db_session.add_all([rule1, rule2])
    db_session.commit()

    # Case-insensitive substring matches
    matches1 = match_rules("What is the price of this product?", db_session)
    assert len(matches1) == 1
    assert matches1[0].keyword == "PRICE"

    matches2 = match_rules("Need INFO please!", db_session)
    assert len(matches2) == 1
    assert matches2[0].keyword == "info"

    matches_both = match_rules("What is the PRICE and INFO?", db_session)
    assert len(matches_both) == 2

    matches_none = match_rules("Hello world", db_session)
    assert len(matches_none) == 0
