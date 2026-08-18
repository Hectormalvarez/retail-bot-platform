"""Tests for the Address CRUD endpoints."""

import pytest

from .factories import AddressFactory, TelegramUserFactory


@pytest.mark.django_db
def test_address_crud_full_flow(api_client, db):
    """POST → GET → filter → DELETE lifecycle for addresses."""
    user = TelegramUserFactory(telegram_id=500, first_name="Addr User")

    # Create
    payload = {
        "user": user.telegram_id,
        "label": "Home",
        "full_address": "123 Test Ave, Springfield",
    }
    res = api_client.post("/api/addresses/", payload, format="json")
    assert res.status_code == 201
    addr_id = res.data["id"]

    # Read single
    res = api_client.get(f"/api/addresses/{addr_id}/")
    assert res.status_code == 200
    assert res.data["label"] == "Home"

    # List filtered by user
    res = api_client.get(f"/api/addresses/?user={user.telegram_id}")
    assert res.status_code == 200
    assert len(res.data) == 1
    assert res.data[0]["id"] == addr_id

    # Delete
    res = api_client.delete(f"/api/addresses/{addr_id}/")
    assert res.status_code == 204

    # Verify deleted
    res = api_client.get(f"/api/addresses/{addr_id}/")
    assert res.status_code == 404


@pytest.mark.django_db
def test_address_filter_by_other_user_returns_empty(api_client, db):
    """GET /api/addresses/?user=<other> returns empty for a different user."""
    user_a = TelegramUserFactory(telegram_id=501)
    user_b = TelegramUserFactory(telegram_id=502)
    AddressFactory(user=user_a, label="Office", full_address="456 Work Rd")

    res = api_client.get(f"/api/addresses/?user={user_b.telegram_id}")
    assert res.status_code == 200
    assert res.data == []
