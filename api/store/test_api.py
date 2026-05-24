import pytest
from rest_framework.test import APIClient
from store.models import Category


@pytest.mark.django_db
def test_catalog_api_flow():
    client = APIClient()

    # 1. Seed a category directly into the test database
    category = Category.objects.create(name="Apparel", slug="apparel")

    # 2. Test writing a product record through the read-write viewset
    product_payload = {
        "name": "Platform T-Shirt",
        "description": "High quality cotton tee",
        "price": "25.00",
        "stock": 100,
        "category": category.id,
    }
    response = client.post("/api/products/", product_payload, format="json")
    assert response.status_code == 201
    assert response.data["category_name"] == "Apparel"

    # 3. Test reading the catalog back out using the filtering engine
    get_response = client.get(f"/api/products/?category={category.id}")
    assert get_response.status_code == 200
    assert len(get_response.data) == 1
