import pytest
from rest_framework.test import APIClient
from store.models import Cart, Category, Product, TelegramUser


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    return TelegramUser.objects.create(telegram_id=999, first_name="Fixture User")


@pytest.fixture
def test_category(db):
    return Category.objects.create(name="Tech", slug="tech")


@pytest.fixture
def test_product(db, test_category):
    return Product.objects.create(
        category=test_category, name="Fixture Product", price="100.00", stock=5
    )


@pytest.fixture
def test_cart(db, test_user):
    return Cart.objects.create(user=test_user)
