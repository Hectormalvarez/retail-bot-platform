"""Tests for API key authentication on all endpoints."""

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_product_list_requires_auth():
    """GET /api/products/ without API key returns 401."""
    client = APIClient()
    res = client.get("/api/products/")
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_cart_requires_auth():
    """GET /api/carts/ without API key returns 401."""
    client = APIClient()
    res = client.get("/api/carts/")
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_order_requires_auth():
    """GET /api/orders/ without API key returns 401."""
    client = APIClient()
    res = client.get("/api/orders/")
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_address_requires_auth():
    """GET /api/addresses/ without API key returns 401."""
    client = APIClient()
    res = client.get("/api/addresses/")
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_config_requires_auth():
    """GET /api/config/ without API key returns 401."""
    client = APIClient()
    res = client.get("/api/config/")
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_valid_api_key_grants_access(db):
    """GET /api/products/ with a valid API key returns 200."""
    from django.conf import settings

    client = APIClient(HTTP_X_API_KEY=settings.API_KEY)
    res = client.get("/api/products/")
    assert res.status_code == 200


@pytest.mark.django_db
def test_invalid_api_key_returns_401():
    """GET /api/products/ with an invalid API key returns 401."""
    client = APIClient(HTTP_X_API_KEY="wrong-key")
    res = client.get("/api/products/")
    assert res.status_code in (401, 403)
