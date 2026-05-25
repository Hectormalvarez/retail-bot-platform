import pytest
from rest_framework.test import APIClient
from store.models import Category, Product, TelegramUser, Cart, CartItem, Order

@pytest.mark.django_db
def test_checkout_happy_path_creates_pending_order():
    client = APIClient()
    user = TelegramUser.objects.create(telegram_id=111, first_name="Test")
    category = Category.objects.create(name="Tech", slug="tech")
    product = Product.objects.create(category=category, name="Laptop", price="1000.00", stock=5)
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, product=product, quantity=2)

    payload = {"user": 111, "shipping_address": "123 Main St"}
    res = client.post("/api/orders/", payload, format="json")

    assert res.status_code == 201
    assert res.data["status"] == "PENDING"
    assert float(res.data["total_amount"]) == 2000.00
    
    product.refresh_from_db()
    assert product.stock == 3
    assert cart.items.count() == 0

@pytest.mark.django_db
def test_checkout_insufficient_stock_rolls_back():
    client = APIClient()
    user = TelegramUser.objects.create(telegram_id=222, first_name="Test")
    category = Category.objects.create(name="Tech", slug="tech")
    product = Product.objects.create(category=category, name="Mouse", price="50.00", stock=1)
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, product=product, quantity=2)

    payload = {"user": 222, "shipping_address": "456 Side St"}
    res = client.post("/api/orders/", payload, format="json")

    assert res.status_code == 400
    assert "Insufficient stock" in res.data["error"]
    
    product.refresh_from_db()
    assert product.stock == 1
    assert cart.items.count() == 1

@pytest.mark.django_db
def test_checkout_empty_cart_fails():
    client = APIClient()
    user = TelegramUser.objects.create(telegram_id=333, first_name="Test")
    Cart.objects.create(user=user)

    payload = {"user": 333, "shipping_address": "789 Empty St"}
    res = client.post("/api/orders/", payload, format="json")

    assert res.status_code == 400
    assert "empty" in res.data["error"]