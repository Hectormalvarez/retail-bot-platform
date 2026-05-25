from django.db import transaction
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

    def create(self, request, *args, **kwargs):
        user_id = request.data.get("user")
        shipping_address = request.data.get("shipping_address")

        try:
            user = TelegramUser.objects.get(telegram_id=user_id)
            cart = Cart.objects.get(user=user)
        except (TelegramUser.DoesNotExist, Cart.DoesNotExist):
            return Response(
                {"error": "Invalid user context or missing cart"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart_items = cart.items.select_related("product").all()
        if not cart_items.exists():
            return Response(
                {"error": "Shopping cart is empty"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_amount = sum(item.product.price * item.quantity for item in cart_items)

        with transaction.atomic():
            for item in cart_items:
                product = Product.objects.select_for_update().get(id=item.product.id)

                if product.stock < item.quantity:
                    return Response(
                        {"error": f"Insufficient stock available for {product.name}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                product.stock -= item.quantity
                product.save()

            order = Order.objects.create(
                user=user,
                total_amount=total_amount,
                shipping_address={"raw_address": shipping_address},
            )

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price_at_purchase=item.product.price,
                )

            cart_items.delete()

        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
