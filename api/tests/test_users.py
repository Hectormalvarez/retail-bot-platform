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
