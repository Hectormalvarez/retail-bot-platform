from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.response import Response
from .cart_service import CartService
from .models import Address, Cart, CartItem, Category, Order, Product, TelegramUser
from .serializers import (
    AddressSerializer,
    CartItemSerializer,
    CartSerializer,
    CategorySerializer,
    OrderSerializer,
    ProductSerializer,
    TelegramUserSerializer,
)
from .services import OrderService


class TelegramUserViewSet(viewsets.ModelViewSet):
    queryset = TelegramUser.objects.all()
    serializer_class = TelegramUserSerializer
    lookup_field = "telegram_id"


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ["category"]


class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    lookup_field = "user__telegram_id"


class CartItemViewSet(viewsets.ModelViewSet):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cart_service = CartService()

    def create(self, request, *args, **kwargs):
        cart_id = request.data.get("cart")
        product_id = request.data.get("product")
        if not cart_id or not product_id:
            return Response(
                {"error": "cart and product fields are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quantity = request.data.get("quantity", 1)
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {"error": "quantity must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if quantity <= 0:
            return Response(
                {"error": "quantity must be a positive integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cart = Cart.objects.get(id=cart_id)
        except Cart.DoesNotExist:
            return Response(
                {"error": "Cart not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tg_id = cart.user.telegram_id
        cart_item = self._cart_service.add_or_increment(tg_id, product_id, quantity=quantity)
        if cart_item is None:
            return Response(
                {"error": "Failed to add item — user or product not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(cart_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        item_id = kwargs.get("pk")
        new_qty = request.data.get("quantity")
        if new_qty is None:
            return Response(
                {"error": "quantity field is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            new_qty = int(new_qty)
        except (TypeError, ValueError):
            return Response(
                {"error": "quantity must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart_item = self._cart_service.update_quantity(item_id, new_qty)
        if cart_item is None:
            # Item was deleted (qty <= 0) or didn't exist — 204 is clean in both cases
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = self.get_serializer(cart_item)
        return Response(serializer.data)


class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user_tg_id = self.request.query_params.get("user")
        if user_tg_id is not None:
            qs = qs.filter(user__telegram_id=user_tg_id)
        return qs


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user_tg_id = self.request.query_params.get("user")
        if user_tg_id is not None:
            qs = qs.filter(user__telegram_id=user_tg_id)
        return qs.order_by("-created_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._order_service = OrderService()

    def create(self, request, *args, **kwargs):
        user_id = request.data.get("user")
        shipping_address = request.data.get("shipping_address")

        with transaction.atomic():
            order, error = self._order_service.create_order(user_id, shipping_address)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
