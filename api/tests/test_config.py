"""Tests for the StoreConfig runtime key-value endpoint."""

import pytest

from store.models import StoreConfig


@pytest.mark.django_db
def test_store_config_endpoint_returns_kv_dict(api_client):
    """GET /api/config/ returns a flat key-value dict of all StoreConfig rows."""
    StoreConfig.objects.create(key="venmo_handle", value="@TestVenmo")
    StoreConfig.objects.create(key="zelle_email", value="pay@test.com")

    res = api_client.get("/api/config/")
    assert res.status_code == 200
    assert res.data == {
        "venmo_handle": "@TestVenmo",
        "zelle_email": "pay@test.com",
    }


@pytest.mark.django_db
def test_store_config_empty_returns_empty_dict(api_client):
    """GET /api/config/ with no StoreConfig rows returns an empty dict."""
    res = api_client.get("/api/config/")
    assert res.status_code == 200
    assert res.data == {}
