import pytest
from store.models import CartItem


@pytest.mark.django_db
def test_checkout_happy_path_creates_pending_order(
    api_client, test_user, test_product, test_cart
):
    test_product.stock = 5
    test_product.price = "1000.00"
    test_product.save()
    CartItem.objects.create(cart=test_cart, product=test_product, quantity=2)

    payload = {"user": test_user.telegram_id, "shipping_address": "123 Main St"}
    res = api_client.post("/api/orders/", payload, format="json")

    assert res.status_code == 201
    assert res.data["status"] == "PENDING"
    assert float(res.data["total_amount"]) == 2000.00

    test_product.refresh_from_db()
    assert test_product.stock == 3
    assert test_cart.items.count() == 0


@pytest.mark.django_db
def test_checkout_insufficient_stock_rolls_back(
    api_client, test_user, test_product, test_cart
):
    test_product.stock = 1
    test_product.save()
    CartItem.objects.create(cart=test_cart, product=test_product, quantity=2)

    payload = {"user": test_user.telegram_id, "shipping_address": "456 Side St"}
    res = api_client.post("/api/orders/", payload, format="json")

    assert res.status_code == 400
    assert "Insufficient stock" in res.data["error"]

    test_product.refresh_from_db()
    assert test_product.stock == 1
    assert test_cart.items.count() == 1


@pytest.mark.django_db
def test_checkout_empty_cart_fails(api_client, test_user, test_cart):
    payload = {"user": test_user.telegram_id, "shipping_address": "789 Empty St"}
    res = api_client.post("/api/orders/", payload, format="json")

    assert res.status_code == 400
    assert "empty" in res.data["error"]
