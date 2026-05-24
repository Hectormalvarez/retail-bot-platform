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


@pytest.mark.django_db
def test_user_synchronization_endpoint():
    from rest_framework.test import APIClient

    client = APIClient()
    user_payload = {
        "telegram_id": 999888777,
        "username": "test_shopper",
        "first_name": "Hector",
    }
    # Test creation
    res = client.post("/api/users/", user_payload, format="json")
    assert res.status_code == 201

    # Test retrieval using lookup_field
    get_res = client.get("/api/users/999888777/")
    assert get_res.status_code == 200
    assert get_res.data["username"] == "test_shopper"


@pytest.mark.django_db
def test_cart_operations_and_totals():
    from rest_framework.test import APIClient
    from store.models import Category, Product, TelegramUser, Cart

    client = APIClient()

    # 1. Setup mock models
    user = TelegramUser.objects.create(telegram_id=555, first_name="Hector")
    category = Category.objects.create(name="Gear", slug="gear")
    product = Product.objects.create(
        category=category, name="Cyberpunk Mug", price="20.00", stock=10
    )

    cart = Cart.objects.create(user=user)

    # 2. Test adding a line item to the cart via API
    item_payload = {"cart": cart.id, "product": product.id, "quantity": 2}
    item_res = client.post("/api/cart-items/", item_payload, format="json")
    assert item_res.status_code == 201

    # 3. Verify lookup via user's explicit telegram_id field
    cart_res = client.get(f"/api/carts/{user.telegram_id}/")
    assert cart_res.status_code == 200
    assert cart_res.data["cart_total"] == 40.00
    assert cart_res.data["items"][0]["product_name"] == "Cyberpunk Mug"
