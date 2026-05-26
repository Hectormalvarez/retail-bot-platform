import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_user_synchronization_endpoint():
    client = APIClient()
    user_payload = {
        "telegram_id": 999888777,
        "username": "test_shopper",
        "first_name": "Hector",
    }

    res = client.post("/api/users/", user_payload, format="json")
    assert res.status_code == 201

    get_res = client.get("/api/users/999888777/")
    assert get_res.status_code == 200
    assert get_res.data["username"] == "test_shopper"


@pytest.mark.django_db
def test_user_nonexistent_returns_404():
    """GET /api/users/{telegram_id}/ for a non-existent user returns 404."""
    client = APIClient()
    res = client.get("/api/users/9999999/")
    assert res.status_code == 404


@pytest.mark.django_db
def test_user_duplicate_telegram_id_returns_400():
    """POST /api/users/ with a duplicate telegram_id returns 400."""
    client = APIClient()
    user_payload = {
        "telegram_id": 100,
        "username": "dup_user",
        "first_name": "Dup",
    }
    res = client.post("/api/users/", user_payload, format="json")
    assert res.status_code == 201

    # Same telegram_id again
    res = client.post("/api/users/", user_payload, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_user_missing_required_fields_returns_400():
    """POST /api/users/ without required fields returns 400."""
    client = APIClient()
    # Missing telegram_id and first_name
    res = client.post("/api/users/", {"username": "no_id"}, format="json")
    assert res.status_code == 400