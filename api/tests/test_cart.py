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