"""Thin repository wrappers around Django ORM for injectable data access."""

from __future__ import annotations

from decimal import Decimal

from .models import Cart, CartItem, Order, OrderItem, Product, TelegramUser


class DjangoUserRepo:
    """Wraps TelegramUser ORM queries."""

    def get_by_telegram(self, telegram_id: int) -> TelegramUser:
        return TelegramUser.objects.get(telegram_id=telegram_id)


class DjangoCartRepo:
    """Wraps Cart and CartItem ORM queries."""

    def get_by_user(self, user: TelegramUser) -> Cart:
        return Cart.objects.get(user=user)

    def get_items(self, cart: Cart) -> list[CartItem]:
        return list(cart.items.select_related("product").all())

    def delete_items(self, cart: Cart) -> None:
        cart.items.all().delete()


class DjangoProductRepo:
    """Wraps Product ORM queries."""

    def get_by_id(self, product_id: int) -> Product:
        return Product.objects.get(id=product_id)

    def get_for_update(self, product_id: int) -> Product:
        return Product.objects.select_for_update().get(id=product_id)

    def decrement_stock(self, product: Product, quantity: int) -> None:
        product.stock -= quantity
        product.save(update_fields=["stock"])


class DjangoOrderRepo:
    """Wraps Order and OrderItem ORM creation."""

    def create(
        self,
        user: TelegramUser,
        total_amount: Decimal,
        shipping_address: str,
    ) -> Order:
        return Order.objects.create(
            user=user,
            total_amount=total_amount,
            shipping_address={"raw_address": shipping_address},
        )

    def create_item(
        self,
        order: Order,
        product: Product,
        quantity: int,
        price_at_purchase: Decimal,
    ) -> OrderItem:
        return OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price_at_purchase=price_at_purchase,
        )