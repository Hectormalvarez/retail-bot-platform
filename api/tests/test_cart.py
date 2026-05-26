import pytest


@pytest.mark.django_db
def test_cart_operations_and_totals(api_client, test_user, test_product, test_cart):
    item_payload = {"cart": test_cart.id, "product": test_product.id, "quantity": 2}
    item_res = api_client.post("/api/cart-items/", item_payload, format="json")
    assert item_res.status_code == 201

    cart_res = api_client.get(f"/api/carts/{test_user.telegram_id}/")
    assert cart_res.status_code == 200
    assert cart_res.data["cart_total"] == float(test_product.price) * 2
    assert cart_res.data["items"][0]["product_name"] == test_product.name


@pytest.mark.django_db
def test_cart_item_missing_fields_returns_400(api_client, test_cart):
    """POST /api/cart-items/ without required fields returns 400."""
    payload = {"cart": test_cart.id}  # missing product and quantity
    res = api_client.post("/api/cart-items/", payload, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_cart_item_nonexistent_product_returns_400(api_client, test_cart):
    """POST /api/cart-items/ with a product that doesn't exist returns 400."""
    payload = {"cart": test_cart.id, "product": 99999, "quantity": 1}
    res = api_client.post("/api/cart-items/", payload, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_cart_item_negative_quantity_returns_400(api_client, test_cart, test_product):
    """POST /api/cart-items/ with negative quantity returns 400."""
    payload = {"cart": test_cart.id, "product": test_product.id, "quantity": -1}
    res = api_client.post("/api/cart-items/", payload, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_cart_item_duplicate_product_increments_quantity(
    api_client, test_cart, test_product, test_cart_item
):
    """Duplicate cart+product pair increments quantity instead of error."""
    payload = {"cart": test_cart.id, "product": test_product.id, "quantity": 1}
    res = api_client.post("/api/cart-items/", payload, format="json")
    assert res.status_code == 201
    # Verify quantity was incremented (was 1, now 2)
    assert res.data["quantity"] == 2


@pytest.mark.django_db
def test_cart_item_delete_returns_204(api_client, test_cart_item):
    """DELETE /api/cart-items/{id}/ removes the item and returns 204."""
    res = api_client.delete(f"/api/cart-items/{test_cart_item.id}/")
    assert res.status_code == 204
    # Verify it's actually gone
    get_res = api_client.get("/api/cart-items/")
    assert get_res.status_code == 200
    ids = [item["id"] for item in get_res.data]
    assert test_cart_item.id not in ids


@pytest.mark.django_db
def test_cart_nonexistent_user_returns_404(api_client):
    """GET /api/carts/{telegram_id}/ for a user that doesn't exist returns 404."""
    res = api_client.get("/api/carts/9999999/")
    assert res.status_code == 404
