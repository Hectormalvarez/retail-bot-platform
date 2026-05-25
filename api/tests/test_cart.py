import pytest
from rest_framework.test import APIClient
from store.models import Category, Product, TelegramUser, Cart


@pytest.mark.django_db
def test_cart_operations_and_totals():
    client = APIClient()

    user = TelegramUser.objects.create(telegram_id=555, first_name="Hector")
    category = Category.objects.create(name="Gear", slug="gear")
    product = Product.objects.create(
        category=category, name="Cyberpunk Mug", price="20.00", stock=10
    )

    cart = Cart.objects.create(user=user)

    item_payload = {"cart": cart.id, "product": product.id, "quantity": 2}
    item_res = client.post("/api/cart-items/", item_payload, format="json")
    assert item_res.status_code == 201

    cart_res = client.get(f"/api/carts/{user.telegram_id}/")
    assert cart_res.status_code == 200
    assert cart_res.data["cart_total"] == 40.00
    assert cart_res.data["items"][0]["product_name"] == "Cyberpunk Mug"
