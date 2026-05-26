import pytest


@pytest.mark.django_db
def test_catalog_api_flow(api_client, test_category):
    # Create a product through the read-write viewset using the fixture category
    product_payload = {
        "name": "Platform T-Shirt",
        "description": "High quality cotton tee",
        "price": "25.00",
        "stock": 100,
        "category": test_category.id,
    }
    response = api_client.post("/api/products/", product_payload, format="json")
    assert response.status_code == 201
    assert response.data["category_name"] == test_category.name

    # Read the catalog back using the filtering engine
    get_response = api_client.get(f"/api/products/?category={test_category.id}")
    assert get_response.status_code == 200
    assert len(get_response.data) == 1