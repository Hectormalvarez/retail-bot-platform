from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    AddressViewSet,
    CartItemViewSet,
    CartViewSet,
    CategoryViewSet,
    OrderViewSet,
    ProductViewSet,
    TelegramUserViewSet,
)

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"users", TelegramUserViewSet, basename="user")
router.register(r"carts", CartViewSet, basename="cart")
router.register(r"cart-items", CartItemViewSet, basename="cart-item")
router.register(r"addresses", AddressViewSet, basename="address")
router.register(r"orders", OrderViewSet, basename="order")

urlpatterns = [
    path("", include(router.urls)),
]
