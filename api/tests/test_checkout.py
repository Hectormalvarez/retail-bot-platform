import pytest
from store.models import CartItem
from store.services import OrderService


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


@pytest.mark.django_db
def test_checkout_nonexistent_user_returns_400(api_client):
    """POST /api/orders/ with a user that does not exist returns 400."""
    payload = {"user": 9999999, "shipping_address": "No Man's Land"}
    res = api_client.post("/api/orders/", payload, format="json")
    assert res.status_code == 400
    assert "Invalid user" in res.data["error"]


@pytest.mark.django_db
def test_checkout_missing_fields_returns_400(api_client):
    """POST /api/orders/ without required fields returns 400."""
    payload = {"user": 999}
    res = api_client.post("/api/orders/", payload, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_order_service_create_order_directly(test_user, test_cart, test_product):
    """Integration test OrderService.create_order — cart items become OrderItems."""
    CartItem.objects.create(cart=test_cart, product=test_product, quantity=3)

    service = OrderService()
    order, error = service.create_order(
        user_id=test_user.telegram_id,
        shipping_address="42 Test Ave",
    )

    assert error is None
    assert order is not None
    assert order.user == test_user
    assert order.status == "PENDING"
    assert float(order.total_amount) == float(test_product.price) * 3

    # Verify OrderItems were created
    assert order.items.count() == 1
    order_item = order.items.first()
    assert order_item.product == test_product
    assert order_item.quantity == 3
    assert float(order_item.price_at_purchase) == float(test_product.price)

    # Verify cart was emptied
    assert test_cart.items.count() == 0


@pytest.mark.django_db
def test_order_service_create_order_invalid_user_returns_error(db):
    """OrderService.create_order with a non-existent user returns an error."""
    service = OrderService()
    order, error = service.create_order(
        user_id=9999999,
        shipping_address="Nowhere",
    )
    assert order is None
    assert error is not None
    assert "Invalid user" in error


@pytest.mark.django_db
def test_list_orders_filtered_by_user_and_sorted(api_client, db):
    """GET /api/orders/?user=<id> returns only that user's orders, newest first."""
    from store.models import Order
    from .factories import TelegramUserFactory, OrderFactory

    user_a = TelegramUserFactory(telegram_id=1001, first_name="Alice")
    user_b = TelegramUserFactory(telegram_id=1002, first_name="Bob")

    OrderFactory(user=user_b, total_amount="50.00")
    OrderFactory(user=user_a, total_amount="10.00")
    OrderFactory(user=user_a, total_amount="20.00")
    OrderFactory(user=user_b, total_amount="60.00")
    OrderFactory(user=user_a, total_amount="30.00")

    res = api_client.get(f"/api/orders/?user={user_a.telegram_id}")

    assert res.status_code == 200
    orders = res.data

    # All returned orders belong to user_a
    assert len(orders) == 3
    for order in orders:
        assert order["user"] == user_a.telegram_id

    # Sorted newest-first by created_at
    timestamps = [order["created_at"] for order in orders]
    assert timestamps == sorted(timestamps, reverse=True), (
        "Orders should be sorted newest-first"
    )
