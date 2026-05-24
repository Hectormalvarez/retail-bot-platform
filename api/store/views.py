from rest_framework import viewsets
from .models import Cart, CartItem, Category, Product, TelegramUser
from .serializers import (
    CartItemSerializer,
    CartSerializer,
    CategorySerializer,
    ProductSerializer,
    TelegramUserSerializer,
)


class TelegramUserViewSet(viewsets.ModelViewSet):
    """Handles lifecycle operations for cached Telegram user profiles."""

    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer
    lookup_field = "telegram_id"


class CategoryViewSet(viewsets.ModelViewSet):
    """Handles lifecycle operations for product categories."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    """Handles lifecycle operations for products."""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ["category"]


class CartViewSet(viewsets.ModelViewSet):
    """Handles shopping cart records looked up by the user's Telegram ID."""

    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    lookup_field = "user__telegram_id"


class CartItemViewSet(viewsets.ModelViewSet):
    """Handles adding, adjusting, or deleting specific line items."""

    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
