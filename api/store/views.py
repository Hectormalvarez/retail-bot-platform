from rest_framework import status, viewsets
from rest_framework.response import Response
from .models import Cart, CartItem, Category, Order, OrderItem, Product, TelegramUser
from .serializers import (
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


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._order_service = OrderService()

    def create(self, request, *args, **kwargs):
        user_id = request.data.get("user")
        shipping_address = request.data.get("shipping_address")

        order, error = self._order_service.create_order(user_id, shipping_address)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
