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


@pytest.mark.django_db
def test_products_filter_by_nonexistent_category_returns_400(api_client):
    """Non-existent category returns 400 (django-filter validation)."""
    res = api_client.get("/api/products/?category=99999")
    assert res.status_code == 400


@pytest.mark.django_db
def test_product_nonexistent_returns_404(api_client):
    """GET /api/products/{id}/ for a non-existent product returns 404."""
    res = api_client.get("/api/products/99999/")
    assert res.status_code == 404


@pytest.mark.django_db
def test_categories_empty_list(api_client):
    """GET /api/categories/ when no categories exist returns empty list."""
    res = api_client.get("/api/categories/")
    assert res.status_code == 200
    assert res.data == []


@pytest.mark.django_db
def test_categories_populated_list(api_client, test_category):
    """GET /api/categories/ returns all categories."""
    res = api_client.get("/api/categories/")
    assert res.status_code == 200
    assert len(res.data) == 1
    assert res.data[0]["name"] == test_category.name


@pytest.mark.django_db
def test_products_list_all(api_client, test_product):
    """GET /api/products/ returns all products."""
    res = api_client.get("/api/products/")
    assert res.status_code == 200
    assert len(res.data) >= 1
