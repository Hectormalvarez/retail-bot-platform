"""Business logic extracted from views for reuse and testability."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction

from .models import Cart, Order, OrderItem, Product, TelegramUser


class OrderService:
    """Handles the checkout flow – stock validation, order creation, cart cleanup."""

    @staticmethod
    @transaction.atomic
    def create_order(
        user_id: int, shipping_address: str
    ) -> tuple[Order | None, str | None]:
        """Create an order from the user's cart.

        Returns
        -------
        (order, None) on success, or (None, error_message) on failure.
        """
        try:
            user = TelegramUser.objects.get(telegram_id=user_id)
            cart = Cart.objects.get(user=user)
        except (TelegramUser.DoesNotExist, Cart.DoesNotExist):
            return None, "Invalid user context or missing cart"

        cart_items = cart.items.select_related("product").all()
        if not cart_items.exists():
            return None, "Shopping cart is empty"

        total_amount: Decimal = Decimal("0.00")
        for item in cart_items:
            product = Product.objects.select_for_update().get(id=item.product.id)
            if product.stock < item.quantity:
                return None, f"Insufficient stock available for {product.name}"
            total_amount += product.price * item.quantity

        order = Order.objects.create(
            user=user,
            total_amount=total_amount,
            shipping_address={"raw_address": shipping_address},
        )

        for item in cart_items:
            product = Product.objects.get(id=item.product.id)
            product.stock -= item.quantity
            product.save(update_fields=["stock"])

            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price_at_purchase=item.product.price,
            )

        cart_items.delete()

        return order, None